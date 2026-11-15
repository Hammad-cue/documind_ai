"""
Document-level access control. EVERY list, search and retrieval path goes through
`visible_documents()` so that permission checks happen before any data is read.
"""
from django.db.models import Q

from .models import Document


def visible_documents(user):
    membership = getattr(user, 'membership', None)
    if membership is None:
        return Document.objects.none()

    qs = Document.objects.filter(organization_id=membership.organization_id, is_archived=False)
    if membership.sees_everything:
        return qs

    rule = Q(access_level=Document.Access.ORG) | Q(uploaded_by=user) | Q(allowed_users=user)
    if membership.department_id:
        rule |= Q(access_level=Document.Access.DEPARTMENT, department_id=membership.department_id)
    ids = qs.filter(rule).values('id')
    return Document.objects.filter(id__in=ids)


def can_edit(user, document):
    """Rename, change access, upload new versions, reprocess."""
    m = getattr(user, 'membership', None)
    if m is None or m.organization_id != document.organization_id:
        return False
    if m.is_admin or document.uploaded_by_id == user.id:
        return True
    return m.can_verify and document.department_id is not None and document.department_id == m.department_id
