from django.contrib.auth.models import User
from django.db import models


class Conversation(models.Model):
    """History type 1: a user's search / question sessions."""
    organization = models.ForeignKey('accounts.Organization', on_delete=models.CASCADE, related_name='conversations')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='conversations')
    title = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return self.title or f'Conversation {self.pk}'


class Query(models.Model):
    class Intent(models.TextChoices):
        LOOKUP = 'LOOKUP', 'Record lookup'
        KNOWLEDGE = 'KNOWLEDGE', 'Question answering'
        SEARCH = 'SEARCH', 'Document search'
        COMPARE = 'COMPARE', 'Comparison across records'

    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='queries')
    text = models.TextField()
    intent = models.CharField(max_length=10, choices=Intent.choices)
    plan = models.JSONField(default=dict, blank=True)          # router output (filters, route, fallback)
    scope_document_ids = models.JSONField(default=list, blank=True)
    answer = models.TextField(blank=True)
    sources = models.JSONField(default=list, blank=True)       # cited chunks / fields with page numbers
    results = models.JSONField(default=list, blank=True)       # record rows or document hits
    latency_ms = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']
