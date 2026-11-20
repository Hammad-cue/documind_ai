import difflib
import hashlib
import mimetypes
import os
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Count, Prefetch, Q
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ViewSet

from accounts.models import Department
from accounts.permissions import CanUpload, CanVerify, IsOrgMember
from audit.models import AuditEvent
from ai import llm
from audit.service import record

from .access import can_edit, visible_documents
from .models import Document, DocumentVersion, FieldEdit, RecordField
from .pipeline import changes, policy
from .pipeline.queue import enqueue
from .pipeline.understanding import parse_date, parse_money
from .schema import FIELD_KEYS, FIELD_LABELS, FIELD_TYPES
from .serializers import (DocumentDetailSerializer, DocumentListSerializer, DocumentUpdateSerializer,
                          FieldEditSerializer, FieldSerializer, VersionSerializer)

EXTENSIONS = {'.pdf': 'PDF', '.docx': 'DOCX', '.png': 'IMAGE', '.jpg': 'IMAGE', '.jpeg': 'IMAGE',
              '.tif': 'IMAGE', '.tiff': 'IMAGE', '.webp': 'IMAGE'}
MAGIC = {'PDF': [b'%PDF'], 'DOCX': [b'PK\x03\x04'],
         'IMAGE': [b'\x89PNG', b'\xff\xd8\xff', b'II*\x00', b'MM\x00*', b'RIFF']}


def _validate_upload(f):
    if f is None:
        raise ValidationError({'file': 'A file is required.'})
    ext = os.path.splitext(f.name)[1].lower()
    file_type = EXTENSIONS.get(ext)
    if file_type is None:
        raise ValidationError({'file': f'File type "{ext}" is not supported. Use PDF, DOCX or an image.'})
    if f.size > settings.MAX_UPLOAD_MB * 1024 * 1024:
        raise ValidationError({'file': f'File exceeds the {settings.MAX_UPLOAD_MB} MB limit.'})
    head = f.read(8)
    f.seek(0)
    if not any(head.startswith(m) for m in MAGIC[file_type]):
        raise ValidationError({'file': 'File content does not match its extension.'})
    sha = hashlib.sha256()
    for chunk in f.chunks():
        sha.update(chunk)
    f.seek(0)
    return file_type, sha.hexdigest()


def _bool(v):
    return str(v).lower() in ('1', 'true', 'yes', 'on')


def _int_list(v):
    if v in (None, ''):
        return []
    raw = v if isinstance(v, (list, tuple)) else [v]
    items = [part for item in raw for part in str(item).split(',')]
    try:
        return [int(x) for x in items if str(x).strip()]
    except ValueError:
        raise ValidationError({'allowed_user_ids': 'Must be a list of user ids.'})



def _in_background(fn, *args):
    """Run slow follow-up work (LLM calls for many records) without holding up the request."""
    import threading

    from django.db import connection

    def run():
        try:
            fn(*args)
        finally:
            connection.close()
    threading.Thread(target=run, daemon=True).start()

class DocumentViewSet(ViewSet):
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    permission_classes = [CanUpload]

    def _visible(self):
        return visible_documents(self.request.user)

    def _get(self, pk):
        return get_object_or_404(self._visible().select_related('department', 'uploaded_by', 'current_version'), pk=pk)

    def _require_edit(self, doc):
        if not can_edit(self.request.user, doc):
            raise PermissionDenied('You cannot modify this document.')

    def _org_users(self, ids):
        org = self.request.user.membership.organization_id
        users = list(User.objects.filter(id__in=ids, membership__organization_id=org))
        if len(users) != len(set(ids)):
            raise ValidationError({'allowed_user_ids': 'Some users are not in your organization.'})
        return users

    def _department(self, dept_id):
        if dept_id in (None, '', 'null'):
            return None
        return get_object_or_404(Department, pk=dept_id, organization=self.request.user.membership.organization)

    # ---- list / create ----
    def list(self, request):
        p = request.query_params
        qs = self._visible().select_related('department', 'uploaded_by').annotate(
            version_count=Count('versions', distinct=True),
            needs_review=Count('current_version__fields', filter=Q(current_version__fields__status='NEEDS_REVIEW'),
                               distinct=True),
        ).prefetch_related(Prefetch('versions', queryset=DocumentVersion.objects.order_by('-number')))
        if p.get('kind'):
            qs = qs.filter(kind=p['kind'])
        if p.get('department'):
            qs = qs.filter(department_id=p['department'])
        if p.get('access_level'):
            qs = qs.filter(access_level=p['access_level'])
        if p.get('q'):
            qs = qs.filter(Q(title__icontains=p['q']) | Q(doc_type__icontains=p['q']) | Q(summary__icontains=p['q']))
        docs = list(qs.order_by('-updated_at')[:500])
        for d in docs:  # use the prefetched versions instead of one query per row
            versions = list(d.versions.all())
            d._latest_cache = versions[0] if versions else None
        return Response(DocumentListSerializer(docs, many=True).data)

    def create(self, request):
        m = request.user.membership
        f = request.FILES.get('file')
        file_type, sha = _validate_upload(f)
        title = (request.data.get('title') or os.path.splitext(f.name)[0]).strip()[:255]
        if Document.objects.filter(organization=m.organization, title__iexact=title, is_archived=False).exists():
            raise ValidationError({'title': f'A document named "{title}" already exists. Upload a new version instead.'})
        access = request.data.get('access_level') or Document.Access.ORG
        if access not in Document.Access.values:
            raise ValidationError({'access_level': 'Invalid access level.'})
        dept = self._department(request.data.get('department')) if 'department' in request.data else m.department
        if access == Document.Access.DEPARTMENT and dept is None:
            raise ValidationError({'department': 'Department-only documents need a department.'})
        allowed = self._org_users(_int_list(request.data.getlist('allowed_user_ids') if hasattr(request.data, 'getlist')
                                            else request.data.get('allowed_user_ids')))
        kind = request.data.get('kind')
        with transaction.atomic():
            doc = Document.objects.create(
                organization=m.organization, department=dept, title=title, access_level=access, uploaded_by=request.user,
                kind=kind if kind in (Document.Kind.RECORD, Document.Kind.REFERENCE) else Document.Kind.UNKNOWN,
                kind_locked=kind in (Document.Kind.RECORD, Document.Kind.REFERENCE),
                doc_type=(request.data.get('doc_type') or '')[:120])
            if allowed:
                doc.allowed_users.set(allowed)
            version = DocumentVersion.objects.create(
                document=doc, number=1, file=f, original_filename=f.name[:255], file_type=file_type, file_size=f.size,
                sha256=sha, marked_handwritten=_bool(request.data.get('marked_handwritten')), uploaded_by=request.user)
        record(request.user, AuditEvent.Action.UPLOAD, doc, request, file=f.name, size=f.size)
        enqueue(version)
        doc.refresh_from_db()
        return Response(DocumentDetailSerializer(doc, context={'request': request}).data, status=201)

    # ---- detail / update / archive ----
    def retrieve(self, request, pk=None):
        doc = self._get(pk)
        record(request.user, AuditEvent.Action.VIEW, doc, request)
        return Response(DocumentDetailSerializer(doc, context={'request': request}).data)

    def partial_update(self, request, pk=None):
        doc = self._get(pk)
        self._require_edit(doc)
        s = DocumentUpdateSerializer(data=request.data, partial=True)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        before = {'title': doc.title, 'access_level': doc.access_level, 'department': doc.department_id,
                  'allowed_users': sorted(doc.allowed_users.values_list('id', flat=True)), 'kind': doc.kind}
        if 'title' in d:
            doc.title = d['title']
        if 'doc_type' in d:
            doc.doc_type = d['doc_type']
        if 'kind' in d:
            doc.kind, doc.kind_locked = d['kind'], True
        if 'access_level' in d:
            doc.access_level = d['access_level']
        if 'department' in d:
            doc.department = self._department(d['department'])
        policy_turned_on = d.get('use_as_policy') and not doc.use_as_policy
        if 'use_as_policy' in d:
            if d['use_as_policy'] and doc.kind != Document.Kind.REFERENCE:
                raise ValidationError({'use_as_policy': 'Only reference documents can be used as policies.'})
            doc.use_as_policy = d['use_as_policy']
        if doc.access_level == Document.Access.DEPARTMENT and doc.department_id is None:
            raise ValidationError({'department': 'Department-only documents need a department.'})
        doc.save()
        if 'allowed_user_ids' in d:
            doc.allowed_users.set(self._org_users(d['allowed_user_ids']))
        after = {'title': doc.title, 'access_level': doc.access_level, 'department': doc.department_id,
                 'allowed_users': sorted(doc.allowed_users.values_list('id', flat=True)), 'kind': doc.kind}
        access_changed = any(before[k] != after[k] for k in ('access_level', 'department', 'allowed_users'))
        record(request.user, AuditEvent.Action.ACCESS_CHANGE if access_changed else AuditEvent.Action.UPDATE_DOCUMENT,
               doc, request, before=before, after=after)
        if policy_turned_on and doc.current_version_id:
            _in_background(policy.recheck_organization, doc.organization_id)
        return Response(DocumentDetailSerializer(doc, context={'request': request}).data)

    def destroy(self, request, pk=None):
        """Records are never hard-deleted: they are archived and stay in the audit trail."""
        doc = self._get(pk)
        self._require_edit(doc)
        doc.is_archived = True
        doc.save(update_fields=['is_archived', 'updated_at'])
        record(request.user, AuditEvent.Action.ARCHIVE, doc, request)
        return Response(status=status.HTTP_204_NO_CONTENT)

    # ---- versions (history type 2) ----
    @action(detail=True, methods=['get', 'post'])
    def versions(self, request, pk=None):
        doc = self._get(pk)
        if request.method == 'GET':
            return Response(VersionSerializer(doc.versions.all(), many=True).data)
        self._require_edit(doc)
        f = request.FILES.get('file')
        file_type, sha = _validate_upload(f)
        latest = doc.latest_version
        if latest and latest.sha256 == sha:
            raise ValidationError({'file': 'This file is identical to the latest version.'})
        with transaction.atomic():
            number = (latest.number if latest else 0) + 1
            version = DocumentVersion.objects.create(
                document=doc, number=number, file=f, original_filename=f.name[:255], file_type=file_type,
                file_size=f.size, sha256=sha, uploaded_by=request.user,
                marked_handwritten=_bool(request.data.get('marked_handwritten')),
                change_note=(request.data.get('change_note') or '')[:300])
        record(request.user, AuditEvent.Action.NEW_VERSION, doc, request, version=number, file=f.name)
        enqueue(version)
        return Response(VersionSerializer(version).data, status=201)

    @action(detail=True, methods=['get'])
    def compare(self, request, pk=None):
        """What changed between two versions: extracted facts, page text and (with ?summary=1) a short summary."""
        doc = self._get(pk)
        try:
            a = doc.versions.get(number=int(request.query_params.get('a')))
            b = doc.versions.get(number=int(request.query_params.get('b')))
        except (TypeError, ValueError, DocumentVersion.DoesNotExist):
            raise ValidationError({'detail': 'Pass ?a=<version>&b=<version> with existing version numbers.'})
        out = changes.diff_versions(a, b)
        if request.query_params.get('summary') in ('1', 'true'):
            try:
                out['summary'] = changes.summary_between(a, b, doc.title)
            except llm.LLMError:
                out['summary'] = ''
        return Response(out)

    @action(detail=True, methods=['post'], url_path='check-policies')
    def check_policies(self, request, pk=None):
        """Re-check the current version of a record against the organization's policy documents."""
        doc = self._get(pk)
        m = request.user.membership
        if not (can_edit(request.user, doc) or m.can_verify):
            raise PermissionDenied('Only managers, admins and the uploader can run the policy check.')
        if doc.kind != Document.Kind.RECORD or doc.current_version is None:
            raise ValidationError({'detail': 'Only processed records can be checked against policies.'})
        try:
            policy.check_policies(doc.current_version, notify_people=False)
        except llm.LLMError as exc:
            return Response({'detail': f'The language model is unavailable right now ({exc}).'}, status=503)
        return Response(DocumentDetailSerializer(doc, context={'request': request}).data['policy'])

    @action(detail=True, methods=['get'])
    def file(self, request, pk=None):
        """Files are only served through this permission-checked endpoint (never public URLs)."""
        doc = self._get(pk)
        number = request.query_params.get('version')
        version = doc.versions.filter(number=number).first() if number else (doc.current_version or doc.latest_version)
        if version is None:
            return Response(status=404)
        download = _bool(request.query_params.get('download'))
        record(request.user, AuditEvent.Action.DOWNLOAD if download else AuditEvent.Action.VIEW, doc, request,
               version=version.number, mode='download' if download else 'open-file')
        content_type = mimetypes.guess_type(version.original_filename)[0] or 'application/octet-stream'
        return FileResponse(version.file.open('rb'), as_attachment=download, filename=version.original_filename,
                            content_type=content_type)

    @action(detail=True, methods=['get'])
    def pages(self, request, pk=None):
        doc = self._get(pk)
        number = request.query_params.get('version')
        version = doc.versions.filter(number=number).first() if number else (doc.current_version or doc.latest_version)
        if version is None:
            return Response([])
        return Response([{'number': p.number, 'text': p.text, 'source': p.source, 'ocr_confidence': p.ocr_confidence}
                         for p in version.pages.all()])

    @action(detail=True, methods=['post'])
    def reprocess(self, request, pk=None):
        doc = self._get(pk)
        self._require_edit(doc)
        version = doc.latest_version
        version.status = DocumentVersion.Status.QUEUED
        version.save(update_fields=['status'])
        record(request.user, AuditEvent.Action.REPROCESS, doc, request, version=version.number)
        enqueue(version)
        return Response({'detail': 'Queued for processing.'})


# ---------------- records (structured fields) ----------------

def _apply_value(field, value):
    t = FIELD_TYPES.get(field.key, 'text')
    field.value_date = parse_date(value) if t == 'date' else None
    field.value_number = parse_money(value) if t == 'money' else None
    if t == 'date' and value and field.value_date is None:
        raise ValidationError({'value': 'Could not understand this date. Use YYYY-MM-DD.'})
    field.value_text = field.value_date.isoformat() if field.value_date else value


class RecordListView(APIView):
    """One row per record document with its key fields (the organization's records register)."""
    permission_classes = [IsOrgMember]

    def get(self, request):
        p = request.query_params
        docs = visible_documents(request.user).filter(kind=Document.Kind.RECORD).select_related('current_version', 'department')
        if p.get('q'):
            docs = docs.filter(Q(title__icontains=p['q']) | Q(doc_type__icontains=p['q']))
        if p.get('doc_type'):
            docs = docs.filter(doc_type__icontains=p['doc_type'])
        if p.get('expiring_within'):
            today = timezone.localdate()
            end = today + timedelta(days=int(p['expiring_within']))
            ids = RecordField.objects.filter(key='expiry_date', value_date__gte=today, value_date__lte=end).values('version_id')
            docs = docs.filter(current_version_id__in=ids)
        fields = RecordField.objects.filter(version_id__in=docs.values('current_version_id'))
        by_version = {}
        for f in fields:
            by_version.setdefault(f.version_id, {})[f.key] = {
                'id': f.id, 'value': f.value_text, 'status': f.status, 'page': f.source_page}
        from .models import PolicyFinding
        issues = dict(PolicyFinding.objects.filter(version_id__in=docs.values('current_version_id'), status='ISSUE')
                      .values_list('version_id').annotate(n=Count('id')))
        rows = []
        for d in docs.order_by('title')[:500]:
            values = by_version.get(d.current_version_id, {})
            rows.append({'id': d.id, 'title': d.title, 'doc_type': d.doc_type,
                         'department': d.department.name if d.department_id else None,
                         'ready': d.current_version_id is not None, 'fields': values,
                         'needs_review': sum(1 for v in values.values() if v['status'] == 'NEEDS_REVIEW'),
                         'policy_issues': issues.get(d.current_version_id, 0)})
        if p.get('needs_review') == '1':
            rows = [r for r in rows if r['needs_review']]
        return Response(rows)


class ReviewQueueView(APIView):
    """Fields the system is not sure about, waiting for a person to verify or correct."""
    permission_classes = [CanVerify]

    def get(self, request):
        if not request.user.membership.can_verify:
            raise PermissionDenied('Only managers and admins can review records.')
        docs = visible_documents(request.user)
        qs = RecordField.objects.filter(status=RecordField.Status.NEEDS_REVIEW,
                                        version_id__in=docs.values('current_version_id')) \
            .select_related('version__document').order_by('version__document__title', 'id')[:300]
        out = []
        for f in qs:
            row = FieldSerializer(f).data
            row.update({'document_id': f.version.document_id, 'document_title': f.version.document.title,
                        'version': f.version.number,
                        'page_source': f.version.pages.filter(number=f.source_page).values_list('source', flat=True).first()})
            out.append(row)
        return Response(out)


class FieldView(APIView):
    """Verify or correct one extracted field. Every change is stored in FieldEdit (history type 3)."""
    permission_classes = [CanVerify]

    def _field(self, request, pk):
        docs = visible_documents(request.user)
        return get_object_or_404(RecordField.objects.select_related('version__document'),
                                 pk=pk, version__document__in=docs)

    def patch(self, request, pk):
        field = self._field(request, pk)
        if not request.user.membership.can_verify:
            raise PermissionDenied()
        act = request.data.get('action', 'correct')
        reason = (request.data.get('reason') or '')[:300]
        old_value, old_status = field.value_text, field.status
        if act == 'verify':
            field.status = RecordField.Status.VERIFIED
            audit_action = AuditEvent.Action.FIELD_VERIFY
        elif act == 'correct':
            value = str(request.data.get('value', '')).strip()
            if not value:
                raise ValidationError({'value': 'A value is required.'})
            _apply_value(field, value)
            field.status = RecordField.Status.CORRECTED
            field.confidence = 1.0
            if request.data.get('page'):
                field.source_page = int(request.data['page'])
            audit_action = AuditEvent.Action.FIELD_EDIT
        else:
            raise ValidationError({'action': 'Use "verify" or "correct".'})
        field.save()
        FieldEdit.objects.create(field=field, old_value=old_value, new_value=field.value_text, old_status=old_status,
                                 new_status=field.status, reason=reason, edited_by=request.user)
        record(request.user, audit_action, field.version.document, request, field=field.key,
               old=old_value, new=field.value_text, reason=reason)
        return Response(FieldSerializer(field).data)


class FieldCreateView(APIView):
    """Add a field the extractor missed."""
    permission_classes = [CanVerify]

    def post(self, request):
        if not request.user.membership.can_verify:
            raise PermissionDenied()
        doc = get_object_or_404(visible_documents(request.user), pk=request.data.get('document_id'))
        key = request.data.get('key')
        if key not in FIELD_KEYS:
            raise ValidationError({'key': 'Unknown field.'})
        if doc.current_version_id is None:
            raise ValidationError({'detail': 'Document is not processed yet.'})
        if RecordField.objects.filter(version=doc.current_version, key=key).exists():
            raise ValidationError({'key': 'This field already exists; edit it instead.'})
        value = str(request.data.get('value', '')).strip()
        if not value:
            raise ValidationError({'value': 'A value is required.'})
        field = RecordField(version=doc.current_version, key=key, label=FIELD_LABELS[key], confidence=1.0,
                            status=RecordField.Status.CORRECTED, grounded=False,
                            source_page=int(request.data['page']) if request.data.get('page') else None)
        _apply_value(field, value)
        field.save()
        FieldEdit.objects.create(field=field, old_value='', new_value=field.value_text, old_status='',
                                 new_status=field.status, reason='added manually', edited_by=request.user)
        record(request.user, AuditEvent.Action.FIELD_EDIT, doc, request, field=key, old='', new=field.value_text)
        return Response(FieldSerializer(field).data, status=201)


class FieldHistoryView(APIView):
    permission_classes = [IsOrgMember]

    def get(self, request, pk):
        field = get_object_or_404(RecordField, pk=pk, version__document__in=visible_documents(request.user))
        return Response(FieldEditSerializer(field.edits.select_related('edited_by'), many=True).data)
