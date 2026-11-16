from django.contrib.auth.models import User
from django.db import models


class Notification(models.Model):
    """An in-app message for one person (expiry reminders, processing results, review requests)."""

    class Kind(models.TextChoices):
        EXPIRY = 'EXPIRY', 'Agreement expiring'
        NOTICE = 'NOTICE', 'Notice deadline'
        PROCESSED = 'PROCESSED', 'Document ready'
        FAILED = 'FAILED', 'Processing failed'
        REVIEW = 'REVIEW', 'Needs review'

    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    organization = models.ForeignKey('accounts.Organization', on_delete=models.CASCADE, related_name='notifications')
    kind = models.CharField(max_length=10, choices=Kind.choices)
    title = models.CharField(max_length=200)
    body = models.CharField(max_length=500, blank=True)
    document = models.ForeignKey('documents.Document', on_delete=models.CASCADE, null=True, blank=True, related_name='+')
    link = models.CharField(max_length=300, blank=True)
    # the same reminder is never sent twice to the same person
    dedupe_key = models.CharField(max_length=120, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    read_at = models.DateTimeField(null=True, blank=True)
    emailed = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']
        constraints = [models.UniqueConstraint(fields=['recipient', 'dedupe_key'], condition=~models.Q(dedupe_key=''),
                                               name='unique_notification_per_recipient')]

    def __str__(self):
        return f'{self.recipient} · {self.title}'
