from django.contrib.auth.models import User
from django.db import models


class AuditEvent(models.Model):
    """Append-only log of who did what. History type 4."""

    class Action(models.TextChoices):
        LOGIN = 'LOGIN'
        UPLOAD = 'UPLOAD'
        NEW_VERSION = 'NEW_VERSION'
        VIEW = 'VIEW'
        DOWNLOAD = 'DOWNLOAD'
        SEARCH = 'SEARCH'
        FIELD_EDIT = 'FIELD_EDIT'
        FIELD_VERIFY = 'FIELD_VERIFY'
        UPDATE_DOCUMENT = 'UPDATE_DOCUMENT'
        ACCESS_CHANGE = 'ACCESS_CHANGE'
        ARCHIVE = 'ARCHIVE'
        REPROCESS = 'REPROCESS'
        MEMBER_ADD = 'MEMBER_ADD'
        MEMBER_UPDATE = 'MEMBER_UPDATE'
        DEPARTMENT_CHANGE = 'DEPARTMENT_CHANGE'

    organization = models.ForeignKey('accounts.Organization', on_delete=models.CASCADE, related_name='audit_events')
    actor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='audit_events')
    actor_name = models.CharField(max_length=150, blank=True)  # kept even if user is deleted
    action = models.CharField(max_length=20, choices=Action.choices)
    target_type = models.CharField(max_length=40, blank=True)
    target_id = models.CharField(max_length=40, blank=True)
    target_label = models.CharField(max_length=300, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['organization', 'action', '-created_at'])]

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise ValueError('Audit events are append-only and cannot be modified.')
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError('Audit events are append-only and cannot be deleted.')

    def __str__(self):
        return f'{self.created_at:%Y-%m-%d %H:%M} {self.actor_name} {self.action} {self.target_label}'
