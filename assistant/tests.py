import json
import tempfile
from pathlib import Path
from datetime import date

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from assistant import engine, retrieval, router
from documents.models import Document, RecordField
from documents.testutils import OrgFixture, pdf_upload

NO_LLM = dict(PROCESS_INLINE=True, LLM_PROVIDER='none', VISION_PROVIDER='none',
              MEDIA_ROOT=Path(tempfile.mkdtemp(prefix='docuvault-test-')))


class HeuristicRouterTests(TestCase):
    def test_lookup_questions(self):
        p = router.heuristic_plan('When was the NDA with Acme signed?')
        self.assertEqual(p['intent'], 'LOOKUP')
        self.assertEqual(p['field'], 'signed_date')
        self.assertEqual(p['party'], 'Acme')

    def test_string_null_from_llm_is_treated_as_missing(self):
        self.assertIsNone(router._clean('null'))
        self.assertIsNone(router._clean(' None '))
        self.assertEqual(router._clean('Acme'), 'Acme')

    def test_search_and_knowledge(self):
        self.assertEqual(router.heuristic_plan('Find the lease for the Lahore office')['intent'], 'SEARCH')
        self.assertEqual(router.heuristic_plan('What makes an agreement void under the law?')['intent'], 'KNOWLEDGE')


@override_settings(**NO_LLM)
class AssistantTests(TestCase):
    def setUp(self):
        self.f = OrgFixture()
        c = APIClient()
        c.force_authenticate(self.f.manager)
        secret = ['SECRET SETTLEMENT\nThe settlement amount payable to the claimant is PKR 9,000,000 '
                  'and the codeword is pineapple-zebra.']
        public = ['NON-DISCLOSURE AGREEMENT\nThis agreement is between Acme Corp and Beta Traders.\n'
                  'IN WITNESS WHEREOF signed on 12 March 2025.']
        r1 = c.post('/api/documents/', {'file': pdf_upload('s.pdf', secret), 'title': 'Settlement',
                                        'access_level': 'DEPARTMENT', 'department': self.f.legal.id}, format='multipart')
        r2 = c.post('/api/documents/', {'file': pdf_upload('n.pdf', public), 'title': 'Acme NDA', 'kind': 'RECORD',
                                        'doc_type': 'Non-Disclosure Agreement'}, format='multipart')
        self.secret = Document.objects.get(pk=r1.json()['id'])
        self.nda = Document.objects.get(pk=r2.json()['id'])
        RecordField.objects.create(version=self.nda.current_version, key='signed_date', label='Signing date',
                                   value_text='2025-03-12', value_date=date(2025, 3, 12), source_page=1,
                                   status=RecordField.Status.VERIFIED, confidence=1.0)

    def test_retrieval_never_returns_forbidden_chunks(self):
        hits = retrieval.hybrid_search(self.f.hr_emp, 'settlement amount codeword pineapple-zebra', k=20)
        self.assertNotIn(self.secret.id, {h.chunk.version.document_id for h in hits})
        hits = retrieval.hybrid_search(self.f.outsider, 'settlement amount codeword pineapple-zebra', k=20)
        self.assertEqual(hits, [])
        hits = retrieval.hybrid_search(self.f.legal_emp, 'settlement amount codeword pineapple-zebra', k=5)
        self.assertEqual(hits[0].chunk.version.document_id, self.secret.id)

    def test_forbidden_document_ids_are_ignored(self):
        out = engine.answer(self.f.hr_emp, 'what is the codeword?', document_ids=[self.secret.id])
        self.assertEqual(out['sources'], [])

    def test_lookup_answers_from_records_table(self):
        out = engine.answer(self.f.hr_emp, 'When was the NDA with Acme signed?')
        self.assertEqual(out['intent'], 'LOOKUP')
        self.assertIn('12 March 2025', out['answer'])
        self.assertEqual(out['sources'][0]['document_id'], self.nda.id)

    def test_ask_endpoint_saves_history(self):
        c = APIClient()
        c.force_authenticate(self.f.hr_emp)
        r = c.post('/api/assistant/ask/', {'query': 'When was the NDA with Acme signed?'}, format='json').json()
        r2 = c.post('/api/assistant/ask/', {'query': 'Find the NDA', 'conversation_id': r['conversation_id']},
                    format='json').json()
        self.assertEqual(r2['conversation_id'], r['conversation_id'])
        conv = c.get(f"/api/assistant/conversations/{r['conversation_id']}/").json()
        self.assertEqual(len(conv['queries']), 2)
        other = APIClient()
        other.force_authenticate(self.f.legal_emp)
        self.assertEqual(other.get(f"/api/assistant/conversations/{r['conversation_id']}/").status_code, 404)

    def _stream(self, client, body):
        r = client.post('/api/assistant/ask/stream/', body, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['Content-Type'], 'application/x-ndjson')
        return [json.loads(line) for line in b''.join(r.streaming_content).decode().splitlines() if line.strip()]

    def test_stream_endpoint_sends_events_and_saves_history(self):
        c = APIClient()
        c.force_authenticate(self.f.hr_emp)
        events = self._stream(c, {'query': 'When was the NDA with Acme signed?'})
        types = [e['type'] for e in events]
        self.assertEqual(types[0], 'plan')
        self.assertIn('sources', types)
        self.assertEqual(types[-1], 'done')
        answer = ''.join(e['text'] for e in events if e['type'] == 'delta')
        self.assertIn('12 March 2025', answer)
        done = events[-1]
        self.assertEqual(done['answer'], answer)
        conv = c.get(f"/api/assistant/conversations/{done['conversation_id']}/").json()
        self.assertEqual(len(conv['queries']), 1)

    def test_stream_endpoint_never_leaks_forbidden_documents(self):
        c = APIClient()
        c.force_authenticate(self.f.hr_emp)
        events = self._stream(c, {'query': 'what is the settlement codeword?', 'document_ids': [self.secret.id]})
        sources = [s for e in events if e['type'] == 'sources' for s in e['sources']]
        self.assertNotIn(self.secret.id, {s['document_id'] for s in sources})
        self.assertNotIn('pineapple', ''.join(e.get('text', '') for e in events))

    def test_repeated_question_is_answered_from_cache_per_access(self):
        from django.core.cache import cache
        cache.clear()
        q = 'Find the Acme NDA'
        first = engine.answer(self.f.legal_emp, q)
        self.assertNotIn('cached', first['plan'])
        second = engine.answer(self.f.legal_emp, q)
        self.assertTrue(second['plan'].get('cached'))
        self.assertEqual(second['answer'], first['answer'])
        # someone who can see different documents must not receive the cached answer
        other = engine.answer(self.f.hr_emp, q)
        self.assertNotIn('cached', other['plan'])


class ConfidentSearchTests(TestCase):
    def test_search_requests_without_record_fields_skip_the_llm(self):
        self.assertTrue(router.confident_search('Find the lease for the Lahore office'))
        self.assertTrue(router.confident_search('Show me all handwritten affidavits'))
        self.assertFalse(router.confident_search('Show me the expiry dates of all our leases'))
        self.assertFalse(router.confident_search('When was the NDA with Acme signed?'))
