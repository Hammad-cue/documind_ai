import tempfile
from datetime import date, timedelta
from pathlib import Path

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from documents.models import Document, DocumentVersion, RecordField
from documents.testutils import OrgFixture
from notifications.models import Notification
from notifications.service import notice_days, run_reminders

NO_LLM = dict(PROCESS_INLINE=True, LLM_PROVIDER='none', VISION_PROVIDER='none',
              MEDIA_ROOT=Path(tempfile.mkdtemp(prefix='docuvault-test-')))


class NoticeParsingTests(TestCase):
    def test_notice_periods(self):
        self.assertEqual(notice_days('thirty (30) days written notice'), 30)
        self.assertEqual(notice_days('60 days written notice'), 60)
        self.assertEqual(notice_days('one month written notice'), 30)
        self.assertEqual(notice_days('2 weeks'), 14)
        self.assertIsNone(notice_days('reasonable notice'))


@override_settings(**NO_LLM)
class ReminderTests(TestCase):
    def setUp(self):
        self.f = OrgFixture()
        self.today = date(2026, 6, 1)

    def record(self, title, expiry, notice=None, access=Document.Access.ORG, dept=None):
        doc = Document.objects.create(organization=self.f.org, title=title, kind=Document.Kind.RECORD, access_level=access,
                                      department=dept, uploaded_by=self.f.manager)
        v = DocumentVersion.objects.create(document=doc, number=1, file='x.pdf', original_filename='x.pdf', file_type='PDF',
                                           status=DocumentVersion.Status.READY, uploaded_by=self.f.manager)
        doc.current_version = v
        doc.save()
        RecordField.objects.create(version=v, key='expiry_date', label='Expiry', value_text=str(expiry), value_date=expiry)
        if notice:
            RecordField.objects.create(version=v, key='notice_period', label='Notice', value_text=notice)
        return doc

    def test_expiry_and_notice_reminders(self):
        self.record('Office Lease', self.today + timedelta(days=25), notice='thirty (30) days written notice')
        run_reminders(self.today)
        titles = set(Notification.objects.filter(recipient=self.f.manager).values_list('title', flat=True))
        self.assertIn('Office Lease expires in 25 days', titles)
        # 25 days left but 30 days notice needed -> the notice deadline already passed 5 days ago
        self.assertIn('Notice deadline for Office Lease 5 days ago', titles)
        self.assertTrue(Notification.objects.filter(recipient=self.f.admin, kind='EXPIRY').exists())

    def test_no_duplicates_and_far_dates_ignored(self):
        self.record('Far Contract', self.today + timedelta(days=400))
        self.record('Soon Contract', self.today + timedelta(days=60))
        run_reminders(self.today)
        run_reminders(self.today)
        self.assertEqual(Notification.objects.filter(title__startswith='Far').count(), 0)
        self.assertEqual(Notification.objects.filter(recipient=self.f.manager, title__startswith='Soon').count(), 1)

    def test_people_who_cannot_see_it_are_not_told(self):
        self.record('HR Contract', self.today + timedelta(days=5), access=Document.Access.DEPARTMENT, dept=self.f.hr)
        run_reminders(self.today)
        recipients = set(Notification.objects.values_list('recipient__username', flat=True))
        self.assertIn('admin', recipients)            # admins see everything
        self.assertIn('legal_manager', recipients)    # uploader
        self.assertNotIn('legal_emp', recipients)
        self.assertNotIn('outsider', recipients)

    def test_api_lists_and_marks_read(self):
        self.record('Soon Contract', self.today + timedelta(days=3))
        run_reminders(self.today)
        c = APIClient()
        c.force_authenticate(self.f.manager)
        data = c.get('/api/notifications/').json()
        self.assertEqual(data['unread'], 1)
        c.post('/api/notifications/read/', {}, format='json')
        self.assertEqual(c.get('/api/notifications/').json()['unread'], 0)
        other = APIClient()
        other.force_authenticate(self.f.legal_emp)
        self.assertEqual(other.get('/api/notifications/').json()['unread'], 0)
