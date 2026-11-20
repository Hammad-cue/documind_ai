"""Tests for the policy compliance check and the 'what changed' summary. The LLM is replaced by fixed replies."""
from unittest import mock

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from documents.models import Document, PolicyFinding, RecordField
from documents.pipeline import changes, policy
from documents.testutils import OrgFixture, docx_upload, pdf_upload
from notifications.models import Notification

NO_LLM = dict(PROCESS_INLINE=True, LLM_PROVIDER='none', VISION_PROVIDER='none', LLM_FALLBACK_PROVIDER='')
HANDBOOK = ['CONTRACTS HANDBOOK\n5. Standard NDA term\nOur standard NDA term is two years. '
            'Any term longer than five years needs partner approval.\n'
            '6. Notice periods\nCommercial contracts should allow termination with at least thirty days written notice.']


@override_settings(**NO_LLM)
class PolicyCheckTests(TestCase):
    def setUp(self):
        self.f = OrgFixture()
        self.c = APIClient()
        self.c.force_authenticate(self.f.manager)
        hb = self.c.post('/api/documents/', {'file': pdf_upload('handbook.pdf', HANDBOOK), 'title': 'Handbook',
                                            'kind': 'REFERENCE'}, format='multipart').json()
        self.handbook = Document.objects.get(pk=hb['id'])
        nda = self.c.post('/api/documents/', {'file': pdf_upload('nda.pdf', ['MUTUAL NDA between Acme and Orion. Term: seven (7) years.']),
                                             'title': 'NDA - Orion', 'kind': 'RECORD'}, format='multipart').json()
        self.nda = Document.objects.get(pk=nda['id'])
        RecordField.objects.create(version=self.nda.current_version, key='term', label='Term', value_text='7 years',
                                   source_page=1, confidence=0.9, status='AUTO')

    def _run(self, reply):
        with mock.patch.object(policy.llm, 'is_configured', return_value=True), \
             mock.patch.object(policy.llm, 'chat_json', return_value=reply):
            return policy.check_policies(self.nda.current_version)

    def test_no_policy_document_means_no_check(self):
        self.assertEqual(self._run({'findings': []}), [])
        self.assertIsNone(self.nda.current_version.policy_checked_at)

    def test_findings_are_saved_grounded_and_people_notified(self):
        self.c.patch(f'/api/documents/{self.handbook.id}/', {'use_as_policy': True}, format='json')
        reply = {'findings': [
            {'rule': 'NDA term', 'status': 'issue', 'detail': '7 years needs partner approval', 'source': 'P1',
             'quote': 'Any term longer than five years needs partner approval.'},
            # numbered with the policy's own section number: still found by searching the passages
            {'rule': 'Notice', 'status': 'unclear', 'detail': 'notice not stated', 'source': '6',
             'quote': 'Commercial contracts should allow termination with at least thirty days written notice.'},
            # a rule that is not in the policy is dropped
            {'rule': 'Invented', 'status': 'issue', 'detail': 'x', 'source': 'P1', 'quote': 'All NDAs must be notarised in Karachi.'},
        ]}
        found = self._run(reply)
        self.assertEqual([(f.rule, f.status) for f in found], [('NDA term', 'ISSUE'), ('Notice', 'UNCLEAR')])
        self.assertTrue(all(f.policy_document_id == self.handbook.id and f.policy_page == 1 for f in found))
        self.assertEqual(PolicyFinding.objects.filter(version=self.nda.current_version).count(), 2)
        self.assertTrue(Notification.objects.filter(kind='POLICY', recipient=self.f.manager).exists())
        # records register shows the issue count
        rows = {r['title']: r for r in self.c.get('/api/records/').json()}
        self.assertEqual(rows['NDA - Orion']['policy_issues'], 1)

    def test_duplicate_findings_for_one_rule_are_merged(self):
        self.c.patch(f'/api/documents/{self.handbook.id}/', {'use_as_policy': True}, format='json')
        reply = {'findings': [
            {'rule': 'Term', 'status': 'ok', 'detail': 'a', 'source': 'P1',
             'quote': 'Our standard NDA term is two years. Any term longer than five years needs partner approval.'},
            {'rule': 'Approval', 'status': 'issue', 'detail': 'b', 'source': 'P1',
             'quote': 'Any term longer than five years needs partner approval.'}]}
        found = self._run(reply)
        self.assertEqual([(f.rule, f.status) for f in found], [('Approval', 'ISSUE')])   # the more serious one

    def test_only_reference_documents_can_be_policies_and_employees_cannot_run_the_check(self):
        r = self.c.patch(f'/api/documents/{self.nda.id}/', {'use_as_policy': True}, format='json')
        self.assertEqual(r.status_code, 400)
        emp = APIClient()
        emp.force_authenticate(self.f.legal_emp)
        self.assertEqual(emp.post(f'/api/documents/{self.nda.id}/check-policies/').status_code, 403)


@override_settings(**NO_LLM)
class ChangeSummaryTests(TestCase):
    def setUp(self):
        self.f = OrgFixture()
        self.c = APIClient()
        self.c.force_authenticate(self.f.manager)
        r = self.c.post('/api/documents/', {'file': docx_upload('lease.docx', ['LEASE', 'Rent is PKR 100,000 per month.']),
                                            'title': 'Lease', 'kind': 'RECORD'}, format='multipart').json()
        self.doc = Document.objects.get(pk=r['id'])

    def test_new_version_gets_a_summary_and_compare_can_return_one(self):
        with mock.patch.object(changes.llm, 'is_configured', return_value=True), \
             mock.patch.object(changes.llm, 'chat', return_value='- Rent: PKR 100,000 -> PKR 120,000 (p. 1)') as chat:
            r = self.c.post(f'/api/documents/{self.doc.id}/versions/',
                            {'file': docx_upload('lease2.docx', ['LEASE', 'Rent is PKR 120,000 per month.']),
                             'change_note': 'new rent'}, format='multipart')
            self.assertEqual(r.status_code, 201, r.content)
            v2 = self.doc.versions.get(number=2)
            self.assertIn('120,000', v2.change_summary)
            self.assertEqual(v2.change_summary_from, 1)
            prompt = chat.call_args[0][0][0]['content']
            self.assertIn('-Rent is PKR 100,000 per month.', prompt)
            self.assertIn('+Rent is PKR 120,000 per month.', prompt)
            out = self.c.get(f'/api/documents/{self.doc.id}/compare/', {'a': 1, 'b': 2, 'summary': 1}).json()
        self.assertIn('120,000', out['summary'])
        self.assertEqual(out['page_changes'][0]['status'], 'changed')

    def test_identical_versions_need_no_model(self):
        v = self.doc.current_version
        self.assertEqual(changes.summarize(changes.diff_versions(v, v)), 'The two versions are identical.')
