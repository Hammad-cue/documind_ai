import tempfile
from pathlib import Path
from datetime import date

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from audit.models import AuditEvent
from documents.access import visible_documents
from documents.models import Document, DocumentVersion, FieldEdit, RecordField
from documents.pipeline import chunking
from documents.pipeline.understanding import ground, parse_date
from documents.testutils import OrgFixture, docx_upload, pdf_upload

NO_LLM = dict(PROCESS_INLINE=True, LLM_PROVIDER='none', VISION_PROVIDER='none',
              MEDIA_ROOT=Path(tempfile.mkdtemp(prefix='docuvault-test-')))

NDA_PAGES = [
    'NON-DISCLOSURE AGREEMENT\nThis Agreement is made between Acme Corp and Beta Traders.\n'
    '1. Definitions\nConfidential Information means all business information disclosed by either party.',
    '2. Obligations\nThe receiving party shall keep the information secret for five years.\n'
    '3. Termination\nEither party may terminate with 30 days written notice.',
    'IN WITNESS WHEREOF the parties signed this agreement on 12 March 2025.\nSigned: Ali Khan, Director',
]


class UnitTests(TestCase):
    def test_parse_date_formats(self):
        self.assertEqual(parse_date('2025-03-12'), date(2025, 3, 12))
        self.assertEqual(parse_date('12th day of March, 2025'), date(2025, 3, 12))
        self.assertEqual(parse_date('March 12, 2025'), date(2025, 3, 12))
        self.assertEqual(parse_date('12/03/2025'), date(2025, 3, 12))  # day-first (Pakistan)
        self.assertIsNone(parse_date('sometime next year'))

    def test_grounding_rejects_invented_quotes(self):
        page = 'The parties signed this agreement on 12 March 2025 in Lahore.'
        self.assertTrue(ground('signed this agreement on 12 March 2025', page))
        self.assertFalse(ground('signed on 1 January 2020 in Karachi', page))

    def test_structure_aware_chunking_keeps_sections_and_pages(self):
        body10 = 'All agreements are contracts if made by free consent of parties competent to contract. ' * 3
        body11 = 'Every person is competent to contract who is of the age of majority. ' * 3
        pages = [(1, 'CHAPTER II\nOF CONTRACTS\n10. What agreements are contracts\n' + body10),
                 (2, '11. Who are competent to contract\n' + body11)]
        chunks = chunking.chunk_pages(pages)
        self.assertGreaterEqual(len(chunks), 2)
        sec11 = next(c for c in chunks if '11. Who are competent' in c.text)
        self.assertEqual(sec11.page_start, 2)
        self.assertIn('CHAPTER II', sec11.section_path)
        self.assertIn('11. Who are competent', sec11.section_path)


@override_settings(**NO_LLM)
class AccessControlTests(TestCase):
    def setUp(self):
        self.f = OrgFixture()
        mk = lambda title, access, dept=None: Document.objects.create(
            organization=self.f.org, title=title, access_level=access, department=dept, uploaded_by=self.f.admin)
        self.org_doc = mk('Company Policy', Document.Access.ORG)
        self.legal_doc = mk('Legal Only NDA', Document.Access.DEPARTMENT, self.f.legal)
        self.restricted = mk('Board Minutes', Document.Access.RESTRICTED)
        self.restricted.allowed_users.add(self.f.hr_emp)

    def ids(self, user):
        return set(visible_documents(user).values_list('id', flat=True))

    def test_visibility_matrix(self):
        f = self.f
        everything = {self.org_doc.id, self.legal_doc.id, self.restricted.id}
        self.assertEqual(self.ids(f.admin), everything)
        self.assertEqual(self.ids(f.auditor), everything)
        self.assertEqual(self.ids(f.legal_emp), {self.org_doc.id, self.legal_doc.id})
        self.assertEqual(self.ids(f.hr_emp), {self.org_doc.id, self.restricted.id})
        self.assertEqual(self.ids(f.outsider), set())

    def test_api_hides_and_blocks_other_documents(self):
        c = APIClient()
        c.force_authenticate(self.f.hr_emp)
        listed = {d['id'] for d in c.get('/api/documents/').json()}
        self.assertNotIn(self.legal_doc.id, listed)
        self.assertEqual(c.get(f'/api/documents/{self.legal_doc.id}/').status_code, 404)
        self.assertEqual(c.get(f'/api/documents/{self.legal_doc.id}/file/').status_code, 404)
        c.force_authenticate(self.f.outsider)
        self.assertEqual(c.get(f'/api/documents/{self.org_doc.id}/').status_code, 404)

    def test_archived_documents_disappear(self):
        c = APIClient()
        c.force_authenticate(self.f.admin)
        self.assertEqual(c.delete(f'/api/documents/{self.org_doc.id}/').status_code, 204)
        self.assertNotIn(self.org_doc.id, self.ids(self.f.legal_emp))
        self.assertTrue(Document.objects.filter(pk=self.org_doc.pk).exists())  # archived, not deleted

    def test_employee_cannot_edit_others_document(self):
        c = APIClient()
        c.force_authenticate(self.f.legal_emp)
        r = c.patch(f'/api/documents/{self.legal_doc.id}/', {'access_level': 'ORG'}, format='json')
        self.assertEqual(r.status_code, 403)

    def test_auditor_cannot_upload(self):
        c = APIClient()
        c.force_authenticate(self.f.auditor)
        r = c.post('/api/documents/', {'file': pdf_upload('x.pdf', ['hello world ' * 10])}, format='multipart')
        self.assertEqual(r.status_code, 403)


@override_settings(**NO_LLM)
class PipelineAndHistoryTests(TestCase):
    def setUp(self):
        self.f = OrgFixture()
        self.c = APIClient()
        self.c.force_authenticate(self.f.manager)

    def upload(self, file, **extra):
        r = self.c.post('/api/documents/', {'file': file, **extra}, format='multipart')
        self.assertEqual(r.status_code, 201, r.content)
        return Document.objects.get(pk=r.json()['id'])

    def test_pdf_pipeline_extracts_pages_and_chunks(self):
        doc = self.upload(pdf_upload('Acme NDA.pdf', NDA_PAGES), title='Acme NDA')
        v = doc.versions.get(number=1)
        self.assertEqual(v.status, DocumentVersion.Status.READY, v.error)
        self.assertEqual(v.page_count, 3)
        self.assertEqual(doc.current_version_id, v.id)
        self.assertEqual(doc.kind, Document.Kind.RECORD)  # heuristic classifier
        termination = v.chunks.filter(text__icontains='30 days written notice').first()
        self.assertIsNotNone(termination)
        self.assertEqual(termination.page_start, 2)
        self.assertTrue(v.chunks.exclude(embedding=None).exists())
        self.assertTrue(AuditEvent.objects.filter(action='UPLOAD', target_id=str(doc.id)).exists())

    def test_rejects_wrong_file_types(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        bad = SimpleUploadedFile('virus.exe', b'MZ\x90\x00', content_type='application/octet-stream')
        self.assertEqual(self.c.post('/api/documents/', {'file': bad}, format='multipart').status_code, 400)
        fake = SimpleUploadedFile('fake.pdf', b'not really a pdf', content_type='application/pdf')
        self.assertEqual(self.c.post('/api/documents/', {'file': fake}, format='multipart').status_code, 400)

    def test_versions_and_compare(self):
        doc = self.upload(docx_upload('lease.docx', ['LEASE AGREEMENT', 'Rent is PKR 100,000 per month.']),
                          title='Office Lease', kind='RECORD')
        v1 = doc.versions.get(number=1)
        RecordField.objects.create(version=v1, key='contract_value', label='Contract value', value_text='PKR 100,000')
        r = self.c.post(f'/api/documents/{doc.id}/versions/',
                        {'file': docx_upload('lease-v2.docx', ['LEASE AGREEMENT', 'Rent is PKR 120,000 per month.']),
                         'change_note': 'Rent increased'}, format='multipart')
        self.assertEqual(r.status_code, 201, r.content)
        doc.refresh_from_db()
        self.assertEqual(doc.current_version.number, 2)
        self.assertEqual(doc.versions.count(), 2)  # v1 is kept
        RecordField.objects.create(version=doc.current_version, key='contract_value', label='Contract value',
                                   value_text='PKR 120,000')
        cmp = self.c.get(f'/api/documents/{doc.id}/compare/?a=1&b=2').json()
        self.assertEqual(cmp['field_changes'][0]['from'], 'PKR 100,000')
        self.assertEqual(cmp['field_changes'][0]['to'], 'PKR 120,000')
        self.assertTrue(cmp['page_changes'])

    def test_field_correction_is_recorded_in_history(self):
        doc = self.upload(pdf_upload('nda.pdf', NDA_PAGES), title='NDA')
        field = RecordField.objects.create(version=doc.current_version, key='signed_date', label='Signing date',
                                           value_text='2025-03-21', value_date=date(2025, 3, 21), confidence=0.4,
                                           status=RecordField.Status.NEEDS_REVIEW)
        queue = self.c.get('/api/records/review-queue/').json()
        self.assertIn(field.id, [q['id'] for q in queue])

        r = self.c.patch(f'/api/records/fields/{field.id}/',
                         {'action': 'correct', 'value': '12 March 2025', 'reason': 'Misread handwriting'}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        field.refresh_from_db()
        self.assertEqual(field.value_date, date(2025, 3, 12))
        self.assertEqual(field.status, RecordField.Status.CORRECTED)
        edit = FieldEdit.objects.get(field=field)
        self.assertEqual((edit.old_value, edit.new_value), ('2025-03-21', '2025-03-12'))
        self.assertEqual(edit.edited_by, self.f.manager)
        self.assertTrue(AuditEvent.objects.filter(action='FIELD_EDIT').exists())
        history = self.c.get(f'/api/records/fields/{field.id}/history/').json()
        self.assertEqual(history[0]['reason'], 'Misread handwriting')

    def test_employee_cannot_verify(self):
        doc = self.upload(pdf_upload('nda.pdf', NDA_PAGES), title='NDA')
        field = RecordField.objects.create(version=doc.current_version, key='parties', label='Parties', value_text='x')
        emp = APIClient()
        emp.force_authenticate(self.f.legal_emp)
        r = emp.patch(f'/api/records/fields/{field.id}/', {'action': 'verify'}, format='json')
        self.assertEqual(r.status_code, 403)

    def test_audit_log_is_append_only(self):
        self.upload(pdf_upload('nda.pdf', NDA_PAGES), title='NDA')
        ev = AuditEvent.objects.first()
        ev.action = 'VIEW'
        with self.assertRaises(ValueError):
            ev.save()
        with self.assertRaises(ValueError):
            ev.delete()
        emp = APIClient()
        emp.force_authenticate(self.f.legal_emp)
        self.assertEqual(emp.get('/api/audit/').status_code, 403)
        aud = APIClient()
        aud.force_authenticate(self.f.auditor)
        self.assertGreater(aud.get('/api/audit/').json()['count'], 0)


class ExpiryAndSecondCheckTests(TestCase):
    def _field(self, key, value, conf=0.9, **extra):
        from documents.schema import FIELD_LABELS
        return {'key': key, 'label': FIELD_LABELS[key], 'value_text': value, 'value_date': extra.pop('d', None),
                'value_number': None, 'confidence': conf, 'source_page': 1, 'source_quote': extra.pop('q', 'quote'),
                'grounded': True, 'status': 'AUTO', 'review_reason': ''}

    def test_term_parsing(self):
        from documents.pipeline.understanding import parse_term
        self.assertEqual(parse_term('three (3) years'), ('months', 36))
        self.assertEqual(parse_term('thirty-six months'), ('months', 36))
        self.assertEqual(parse_term('90 days'), ('days', 90))
        self.assertIsNone(parse_term('until terminated by either party'))
        self.assertIsNone(parse_term('reasonable period'))

    def test_expiry_is_calculated_from_start_and_term_and_sent_for_review(self):
        from documents.pipeline.understanding import derive_expiry
        fields = {'effective_date': self._field('effective_date', '2025-04-01', d=date(2025, 4, 1)),
                  'term': self._field('term', '3 years', q='This Agreement shall remain in force for three (3) years')}
        out = derive_expiry(fields)
        self.assertEqual(out['value_date'], date(2028, 3, 31))
        self.assertEqual(out['status'], 'NEEDS_REVIEW')
        self.assertIn('Calculated', out['review_reason'])
        self.assertEqual(out['source_quote'], fields['term']['source_quote'])

    def test_written_expiry_is_never_replaced(self):
        from documents.pipeline.understanding import derive_expiry
        fields = {'effective_date': self._field('effective_date', '2025-04-01', d=date(2025, 4, 1)),
                  'term': self._field('term', '3 years'),
                  'expiry_date': self._field('expiry_date', '2027-12-31', d=date(2027, 12, 31))}
        self.assertIsNone(derive_expiry(fields))

    def test_second_check_sends_unsupported_values_to_review(self):
        from unittest import mock
        from documents.pipeline import understanding
        from documents.pipeline.extract import PageText

        extracted = {'fields': {
            'governing_law': {'value': 'Pakistan', 'page': 1, 'quote': 'governed by the laws of Pakistan', 'confidence': 0.95},
            'notice_period': {'value': '60 days', 'page': 1, 'quote': 'renews for successive one year terms unless 60 days', 'confidence': 0.95}}}
        verdict = {'results': {'governing_law': {'supported': True},
                               'notice_period': {'supported': False, 'reason': 'the quote is about renewal, not termination'}}}
        page = PageText(1, 'This Agreement is governed by the laws of Pakistan. It renews for successive one year terms unless 60 days notice is given.', 'DIGITAL')
        with mock.patch.object(understanding.llm, 'chat_json', side_effect=[extracted, verdict]), \
             mock.patch.object(understanding.llm, 'is_configured', return_value=True):
            fields = {f['key']: f for f in understanding.extract_fields([page])}
        self.assertEqual(fields['governing_law']['status'], 'AUTO')
        self.assertEqual(fields['notice_period']['status'], 'NEEDS_REVIEW')
        self.assertIn('renewal', fields['notice_period']['review_reason'])
