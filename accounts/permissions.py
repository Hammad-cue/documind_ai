from rest_framework.permissions import BasePermission


def membership_of(user):
    return getattr(user, 'membership', None) if user and user.is_authenticated else None


class IsOrgMember(BasePermission):
    message = 'You are not a member of any organization.'

    def has_permission(self, request, view):
        return membership_of(request.user) is not None


class IsOrgAdmin(IsOrgMember):
    message = 'Only organization admins can do this.'

    def has_permission(self, request, view):
        m = membership_of(request.user)
        return m is not None and m.is_admin


class CanUpload(IsOrgMember):
    message = 'Your role cannot upload documents.'

    def has_permission(self, request, view):
        m = membership_of(request.user)
        if m is None:
            return False
        if request.method in ('GET', 'HEAD', 'OPTIONS'):
            return True
        return m.can_upload


class CanVerify(IsOrgMember):
    message = 'Only managers and admins can verify records.'

    def has_permission(self, request, view):
        m = membership_of(request.user)
        if m is None:
            return False
        if request.method in ('GET', 'HEAD', 'OPTIONS'):
            return True
        return m.can_verify


class CanViewAudit(IsOrgMember):
    message = 'Only admins and auditors can view the audit log.'

    def has_permission(self, request, view):
        m = membership_of(request.user)
        return m is not None and m.can_view_audit
