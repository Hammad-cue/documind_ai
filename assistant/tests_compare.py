"""Tests for comparison questions ("Compare the termination notice in all our NDAs")."""
import json
import tempfile
from pathlib import Path
from unittest import mock

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from assistant import compare, engine, router
from assistant.models import Query
from documents.models import Document, RecordField
from documents.testutils import OrgFixture, pdf_upload

NO_LLM = dict(PROCESS_INLINE=True, LLM_PROVIDER='none', VISION_PROVIDER='none', LLM_FALLBACK_PROVIDER='',
              MEDIA_ROOT=Path(tempfile.mkdtemp(prefix='docuvault-test-')))


class CompareRouterTests(TestCase):
    def test_comparison_questions(self):
        p = router.heuristic_plan('Compare the termination notice in all our NDAs')
        self.assertEqual((p['intent'], p['doc_type'], p['fields']), ('COMPARE', 'nda', ['notice_period']))
        p = router.heuristic_plan('Compare the NDAs with Acme and Orion')
        self.assertEqual((p['intent'], p['records']), ('COMPARE', ['Acme', 'Orion']))
        p = router.heuristic_plan('Compare the confidentiality obligations in our NDAs')
        self.assertEqual((p['intent'], p['aspect']), ('COMPARE', 'confidentiality obligations'))
        p = router.heuristic_plan('Compare the termination rights in the NDA and the lease')
        self.assertEqual((p['intent'], p['doc_type']), ('COMPARE', None))      # two types named: no type filter

    def test_look_alikes_are_not_comparisons(self):
        self.assertEqual(router.heuristic_plan('What is the difference between a void agreement and a voidable contract?')['intent'], 'KNOWLEDGE')
        self.assertEqual(router.heuristic_plan('When was the NDA with Acme signed?')['intent'], 'LOOKUP')
        self.assertNotEqual(router.heuristic_plan('Compare void agreements with voidable contracts under the Contract Act')['intent'], 'COMPARE')
        self.assertEqual(router.heuristic_plan('Contrast the confidentiality clauses of the Acme and Orion NDAs')['intent'], 'COMPARE')
        self.assertFalse(router.confident_search('Show the notice periods of our NDAs side by side'))


@override_settings(**NO_LLM)
class CompareAnswerTests(TestCase):
    def setUp(self):
        self.f = OrgFixture()
        c = APIClient()
        c.force_authenticate(self.f.manager)

        def upload(title, text, doc_type, **extra):
            r = c.post('/api/documents/', {'file': pdf_upload(f'{title}.pdf', [text]), 'title': title, 'kind': 'RECORD',
                                           **extra}, format='multipart').json()
            Document.objects.filter(pk=r['id']).update(doc_type=doc_type)
            return Document.objects.get(pk=r['id'])

        # one sentence per line: the test PDF does not wrap long lines
        self.acme = upload('NDA - Acme', 'MUTUAL NDA between Khan & Associates and Acme Corp.\nPurpose: a software '
                           'partnership.\nEither party may terminate with thirty (30) days written notice.', 'Non-Disclosure Agreement')
        self.orion = upload('NDA - Orion', 'MUTUAL NDA between Khan & Associates and Orion Ventures.\nPurpose: a joint '
                            'investment in renewable energy.\nEither party may end this agreement with fifteen (15) days '
                            'written notice.', 'Non-Disclosure Agreement')
        self.lease = upload('Office Lease', 'LEASE of office premises. Ninety (90) days notice.', 'Lease Agreement')
        self.secret = upload('NDA - Secret Bidder', 'NDA with a secret bidder. Notice: seven (7) days.', 'Non-Disclosure Agreement',
                             access_level='DEPARTMENT', department=self.f.legal.id)
        for doc, value, quote in [(self.acme, '30 days written notice', 'thirty (30) days written notice'),
                                  (self.lease, '90 days', 'Ninety (90) days notice'),
                                  (self.secret, '7 days', 'seven (7) days')]:
            RecordField.objects.create(version=doc.current_version, key='notice_period', label='Notice period',
                                       value_text=value, source_page=1, source_quote=quote, confidence=0.9,
                                       status=RecordField.Status.VERIFIED)

    def test_table_rows_come_from_the_records_table(self):
        out = engine.answer(self.f.manager, 'Compare the termination notice in all our NDAs')
        self.assertEqual(out['intent'], 'COMPARE')
        self.assertEqual([c['key'] for c in out['plan']['columns']], ['notice_period'])
        rows = {r['document_title']: r['cells']['notice_period'] for r in out['results']}
        self.assertEqual(set(rows), {'NDA - Acme', 'NDA - Orion', 'NDA - Secret Bidder'})     # the lease is not an NDA
        self.assertEqual((rows['NDA - Acme']['value'], rows['NDA - Acme']['page']), ('30 days written notice', 1))
        self.assertIsNone(rows['NDA - Orion']['value'])          # not extracted, and no model to read it: "Not stated"
        self.assertIn('Compared **3** records', out['answer'])
        cited = {s['document_id'] for s in out['sources']}
        self.assertEqual(cited, {self.acme.id, self.secret.id})
        # the difference is computed from the table, not written by a model
        self.assertIn('shortest NDA - Secret Bidder (7 days) [2], longest NDA - Acme (30 days written notice) [1]. '
                      'Not stated in NDA - Orion.', out['answer'])

    def test_summary_of_dates_and_shared_values(self):
        cell = lambda v, n, d=None: {'value': v, 'source': n, 'date': d}
        rows = [{'document_title': 'A', 'cells': {'expiry_date': cell('31 March 2028', 1, '2028-03-31'), 'governing_law': cell('Pakistan', 2)}},
                {'document_title': 'B', 'cells': {'expiry_date': cell('11 December 2026', 3, '2026-12-11'), 'governing_law': cell('pakistan.', 4)}},
                {'document_title': 'C', 'cells': {'expiry_date': cell(None, None), 'governing_law': cell('England', 5)}}]
        self.assertEqual(compare.describe(rows, {'key': 'expiry_date', 'label': 'Expiry'}),
                         '**Expiry**: earliest B (11 December 2026) [3], latest A (31 March 2028) [1]. Not stated in C.')
        self.assertEqual(compare.describe(rows, {'key': 'governing_law', 'label': 'Law'}),
                         '**Law**: Pakistan in A, B [2][4]; England in C [5].')

    def test_records_named_by_party_type_or_description(self):
        docs, _ = compare.select_documents(self.f.manager, {'records': ['Acme', 'lease']}, None)
        self.assertEqual([d.title for d in docs], ['NDA - Acme', 'Office Lease'])
        docs, _ = compare.select_documents(self.f.manager, {'records': ['office lease', 'Orion NDA']}, None)
        self.assertEqual([d.title for d in docs], ['NDA - Orion', 'Office Lease'])
        p = router.heuristic_plan('Compare the notice in the NDA and the lease')
        self.assertEqual((p['doc_type'], p['records']), (None, ['lease', 'nda']))
        # a free-text type from the model must not hide the records it names
        docs, _ = compare.select_documents(self.f.manager, {'doc_type': 'office lease, Acme NDA',
                                                            'records': ['office lease', 'Acme NDA']}, None)
        self.assertEqual([d.title for d in docs], ['NDA - Acme', 'Office Lease'])

    def test_people_only_compare_records_they_may_open(self):
        out = engine.answer(self.f.hr_emp, 'Compare the termination notice in all our NDAs')
        titles = {r['document_title'] for r in out['results']}
        self.assertEqual(titles, {'NDA - Acme', 'NDA - Orion'})
        self.assertNotIn('7 days', json.dumps(out))

    def test_values_read_from_the_text_must_be_found_in_it(self):
        plan = {'intent': 'COMPARE', 'doc_type': 'nda', 'fields': ['notice_period'], 'records': ['Acme', 'Orion'],
                'aspect': 'purpose'}
        reply = {'answers': [
            {'id': 'Q1', 'value': 'A cloud hosting deal', 'quote': 'Purpose: a cloud hosting deal'},          # invented
            {'id': 'Q2', 'value': '15 days written notice', 'quote': 'end this agreement with fifteen (15) days written notice'},
            {'id': 'Q3', 'value': 'Joint renewable energy investment', 'quote': 'a joint investment in renewable energy'},
        ]}
        with mock.patch.object(compare.llm, 'is_configured', return_value=True), \
             mock.patch.object(compare.llm, 'chat_json', return_value=reply) as read, \
             mock.patch.object(compare.llm, 'chat', return_value='- Orion allows only 15 days [2], half of Acme [1].'):
            answer, sources, rows = compare.run(self.f.manager, plan, 'Compare notice and purpose', None)
        prompt = read.call_args[0][0][0]['content']
        self.assertIn('[Q1] Document: NDA - Acme', prompt)
        cells = {r['document_title']: r['cells'] for r in rows}
        self.assertIsNone(cells['NDA - Acme']['aspect']['value'])                       # quote not in the document
        self.assertEqual(cells['NDA - Orion']['notice_period']['value'], '15 days written notice')
        self.assertEqual(cells['NDA - Orion']['notice_period']['status'], 'TEXT')
        self.assertEqual(cells['NDA - Orion']['aspect']['page'], 1)
        self.assertEqual(len(sources), 3)
        self.assertIn('shortest NDA - Orion (15 days written notice) [2], longest NDA - Acme', answer)
        self.assertIn('**Purpose**: only NDA - Orion states it', answer)      # one statement: nothing for a model to compare

    def test_free_text_points_are_summarized_by_the_model_from_the_cells(self):
        plan = {'intent': 'COMPARE', 'doc_type': 'nda', 'fields': [], 'records': ['Acme', 'Orion'], 'aspect': 'purpose'}
        reply = {'answers': [{'id': 'Q1', 'value': 'Software partnership', 'quote': 'Purpose: a software partnership'},
                             {'id': 'Q2', 'value': 'Renewable energy investment', 'quote': 'a joint investment in renewable energy'}]}
        with mock.patch.object(compare.llm, 'is_configured', return_value=True), \
             mock.patch.object(compare.llm, 'chat_json', return_value=reply), \
             mock.patch.object(compare.llm, 'chat', return_value='- Acme is about software [1]; Orion about energy [2].') as chat:
            answer, sources, rows = compare.run(self.f.manager, plan, 'Compare the purpose of the NDAs', None)
        prompt = chat.call_args[0][0][1]['content']
        self.assertIn('POINT: Purpose', prompt)
        self.assertIn('- NDA - Acme: Software partnership [1]', prompt)
        self.assertIn('Orion about energy [2]', answer)

    def test_stream_endpoint_returns_the_table_and_saves_it(self):
        c = APIClient()
        c.force_authenticate(self.f.legal_emp)
        r = c.post('/api/assistant/ask/stream/', {'query': 'Compare the termination notice in all our NDAs'}, format='json')
        events = [json.loads(x) for x in b''.join(r.streaming_content).decode().splitlines() if x.strip()]
        table = next(e for e in events if e['type'] == 'sources')['results']
        self.assertEqual(len(table), 3)
        done = events[-1]
        self.assertEqual((done['type'], done['intent']), ('done', 'COMPARE'))
        self.assertEqual(done['plan']['columns'][0]['key'], 'notice_period')
        self.assertEqual(Query.objects.get(pk=done['id']).intent, 'COMPARE')

    def test_nothing_to_compare_falls_back_to_the_text(self):
        out = engine.answer(self.f.manager, 'Compare the NDAs with Zenith and Nadir')
        self.assertEqual(out['intent'], 'KNOWLEDGE')
        self.assertIn('fallback', out['plan'])
