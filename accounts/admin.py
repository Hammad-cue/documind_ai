from django.contrib import admin

from audit.models import AuditEvent

from .models import Department, Membership, Organization

admin.site.register([Organization, Department])


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ('user', 'organization', 'role', 'department')
    list_filter = ('organization', 'role')


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'organization', 'actor_name', 'action', 'target_label')
    list_filter = ('organization', 'action')
    search_fields = ('actor_name', 'target_label')

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
