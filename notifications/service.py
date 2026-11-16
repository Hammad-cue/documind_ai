"""
Creating notifications and the expiry / notice-deadline reminder sweep.

The worker runs `run_reminders()` about once an hour, so no separate scheduler is needed.
It can also be run on demand: `python manage.py send_reminders`.
"""
import re
from datetime import date, timedelta

from django.conf import settings
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.db import IntegrityError, transaction
from django.utils import timezone

from accounts.models import Role
from documents.access import visible_documents
from documents.models import Document, RecordField

from .models import Notification

EXPIRY_WINDOWS = [90, 30, 7, 0]   # days before expiry at which people are reminded (0 = today / overdue)

WORD_NUMBERS = {'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6, 'seven': 7, 'eight': 8, 'nine': 9,
                'ten': 10, 'fourteen': 14, 'fifteen': 15, 'twenty': 20, 'thirty': 30, 'forty-five': 45, 'forty five': 45,
                'sixty': 60, 'ninety': 90, 'a': 1}


def notice_days(text):
    """'thirty (30) days written notice' -> 30, 'one month' -> 30, '2 weeks' -> 14. None if unclear."""
    t = (text or '').lower()
    m = re.search(r'(\d{1,3})\s*\)?\s*(day|week|month)', t) or re.search(
        r'\b(' + '|'.join(sorted(map(re.escape, WORD_NUMBERS), key=len, reverse=True)) + r')\b\s*(?:\(\d+\)\s*)?(day|week|month)', t)
    if not m:
        return None
    n = int(m.group(1)) if m.group(1).isdigit() else WORD_NUMBERS[m.group(1)]
    return n * {'day': 1, 'week': 7, 'month': 30}[m.group(2)]


def notify(users, kind, title, body='', document=None, link='', dedupe_key=''):
    """Create one notification per user; silently skips duplicates. Returns the ones created."""
    created = []
    for user in users:
        m = getattr(user, 'membership', None)
        if m is None or not user.is_active:
            continue
        try:
            with transaction.atomic():
                n = Notification.objects.create(recipient=user, organization_id=m.organization_id, kind=kind,
                                                title=title[:200], body=body[:500], document=document,
                                                link=link[:300], dedupe_key=dedupe_key[:120])
        except IntegrityError:
            continue
        created.append(n)
        _maybe_email(n)
    return created


def _maybe_email(n):
    if not getattr(settings, 'REMINDER_EMAILS', False) or not n.recipient.email:
        return
    try:
        send_mail(f'DocuMind: {n.title}', f'{n.body}\n\n{settings.APP_URL}{n.link}', None, [n.recipient.email])
        n.emailed = True
        n.save(update_fields=['emailed'])
    except Exception as exc:  # e-mail is best effort
        print(f'[notifications] email failed: {exc}')


def people_to_remind(document):
    """The uploader, the org's admins, and managers of the document's department — if they can see it."""
    org = document.organization_id
    candidates = User.objects.filter(membership__organization_id=org, is_active=True).filter(
        _recipients_q(document)).distinct()
    return [u for u in candidates if visible_documents(u).filter(pk=document.pk).exists()]


def _recipients_q(document):
    from django.db.models import Q
    q = Q(membership__role=Role.ADMIN)
    if document.uploaded_by_id:
        q |= Q(pk=document.uploaded_by_id)
    if document.department_id:
        q |= Q(membership__role=Role.MANAGER, membership__department_id=document.department_id)
    return q


def _window(days_left):
    """Smallest reminder window the deadline falls in (90 / 30 / 7 / 0), or None if further away."""
    for w in sorted(EXPIRY_WINDOWS):
        if days_left <= w:
            return w
    return None


def _when(days_left):
    if days_left < 0:
        return f'{-days_left} day{"s" if days_left != -1 else ""} ago'
    if days_left == 0:
        return 'today'
    return f'in {days_left} day{"s" if days_left != 1 else ""}'


def run_reminders(today=None):
    """Remind people about agreements that are about to expire, and about the last day to give notice."""
    today = today or timezone.localdate()
    horizon = today + timedelta(days=max(EXPIRY_WINDOWS))
    sent = 0
    docs = Document.objects.filter(is_archived=False, kind=Document.Kind.RECORD, current_version__isnull=False)
    fields = (RecordField.objects.filter(version_id__in=docs.values('current_version_id'), key='expiry_date',
                                         value_date__isnull=False, value_date__lte=horizon,
                                         value_date__gte=today - timedelta(days=7))
              .select_related('version__document'))
    for f in fields:
        doc = f.version.document
        people = people_to_remind(doc)
        link = f'/app/documents/{doc.id}?page={f.source_page or 1}'

        days_left = (f.value_date - today).days
        w = _window(days_left)
        if w is not None:
            sent += len(notify(people, Notification.Kind.EXPIRY, f'{doc.title} expires {_when(days_left)}',
                               f'{doc.doc_type or "Agreement"} ends on {f.value_date:%d %B %Y}. Renew or let it lapse in time.',
                               doc, link, dedupe_key=f'expiry:{f.id}:{f.value_date}:{w}'))

        notice = RecordField.objects.filter(version=f.version, key='notice_period').first()
        nd = notice_days(notice.value_text) if notice else None
        if nd:
            deadline = f.value_date - timedelta(days=nd)
            days_to_deadline = (deadline - today).days
            w2 = _window(days_to_deadline) if days_to_deadline >= -7 else None
            if w2 is not None and w2 <= 30:
                sent += len(notify(people, Notification.Kind.NOTICE, f'Notice deadline for {doc.title} {_when(days_to_deadline)}',
                                   f'It needs {notice.value_text} before it ends on {f.value_date:%d %B %Y}, so the last day to give notice is {deadline:%d %B %Y}.',
                                   doc, link, dedupe_key=f'notice:{f.id}:{deadline}:{w2}'))
    return sent


def document_processed(version):
    """Tell the uploader their document is ready (or failed), and reviewers if facts need checking."""
    doc = version.document
    uploader = [version.uploaded_by] if version.uploaded_by_id else []
    link = f'/app/documents/{doc.id}'
    if version.status == version.Status.FAILED:
        notify(uploader, Notification.Kind.FAILED, f'Couldn’t read {doc.title}', version.error[:300], doc, link,
               dedupe_key=f'failed:{version.id}')
        return
    facts = version.fields.count()
    review = version.fields.filter(status=RecordField.Status.NEEDS_REVIEW).count()
    body = (f'{facts} key fact{"s" if facts != 1 else ""} extracted' + (f', {review} need a human check.' if review else '.')
            if doc.kind == Document.Kind.RECORD else f'{version.page_count} pages indexed — you can ask questions about it now.')
    notify(uploader, Notification.Kind.PROCESSED, f'{doc.title} is ready', body, doc, link, dedupe_key=f'ready:{version.id}')
    if review:
        reviewers = [u for u in people_to_remind(doc) if u.membership.can_verify and u.pk != version.uploaded_by_id]
        notify(reviewers, Notification.Kind.REVIEW, f'{review} fact{"s" if review != 1 else ""} to check in {doc.title}',
               'Read from a scan or handwriting, or the evidence wasn’t found on the page.', doc, '/app/review',
               dedupe_key=f'review:{version.id}')
