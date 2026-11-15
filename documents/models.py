import os
import uuid

from django.contrib.auth.models import User
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVectorField
from django.db import models
from pgvector.django import HnswIndex, VectorField

from accounts.models import Department, Organization


def version_upload_path(instance, filename):
    ext = os.path.splitext(filename)[1].lower()
    doc = instance.document
    return f'org_{doc.organization_id}/doc_{doc.pk}/v{instance.number}_{uuid.uuid4().hex[:8]}{ext}'


class Document(models.Model):
    """A logical document (e.g. "NDA with Acme"). Its file content lives in versions."""

    class Kind(models.TextChoices):
        UNKNOWN = 'UNKNOWN', 'Not classified yet'
        RECORD = 'RECORD', 'Record (contract, NDA, agreement...)'
        REFERENCE = 'REFERENCE', 'Reference (law book, policy, manual...)'

    class Access(models.TextChoices):
        ORG = 'ORG', 'Everyone in the organization'
        DEPARTMENT = 'DEPARTMENT', 'Department only'
        RESTRICTED = 'RESTRICTED', 'Named people only'

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='documents')
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True, related_name='documents')
    title = models.CharField(max_length=255)
    kind = models.CharField(max_length=10, choices=Kind.choices, default=Kind.UNKNOWN)
    kind_locked = models.BooleanField(default=False, help_text='User chose the kind; do not auto-classify.')
    doc_type = models.CharField(max_length=120, blank=True)
    summary = models.TextField(blank=True)
    access_level = models.CharField(max_length=10, choices=Access.choices, default=Access.ORG)
    allowed_users = models.ManyToManyField(User, blank=True, related_name='shared_documents')
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='uploaded_documents')
    current_version = models.ForeignKey('DocumentVersion', on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    is_archived = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return self.title

    @property
    def latest_version(self):
        return self.versions.order_by('-number').first()


class DocumentVersion(models.Model):
    """One uploaded file of a document. History type 2: older versions are never deleted."""

    class FileType(models.TextChoices):
        PDF = 'PDF'
        DOCX = 'DOCX'
        IMAGE = 'IMAGE'

    class Status(models.TextChoices):
        QUEUED = 'QUEUED'
        PROCESSING = 'PROCESSING'
        READY = 'READY'
        FAILED = 'FAILED'

    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='versions')
    number = models.PositiveIntegerField()
    file = models.FileField(upload_to=version_upload_path)
    original_filename = models.CharField(max_length=255)
    file_type = models.CharField(max_length=5, choices=FileType.choices)
    file_size = models.PositiveIntegerField(default=0)
    sha256 = models.CharField(max_length=64, blank=True)
    page_count = models.PositiveIntegerField(default=0)
    marked_handwritten = models.BooleanField(default=False, help_text='Uploader says the document is handwritten.')
    change_note = models.CharField(max_length=300, blank=True)
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='uploaded_versions')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.QUEUED)
    error = models.TextField(blank=True)
    processing_log = models.JSONField(default=list, blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('document', 'number')
        ordering = ['document', '-number']

    def __str__(self):
        return f'{self.document.title} v{self.number}'


class Page(models.Model):
    class Source(models.TextChoices):
        DIGITAL = 'DIGITAL', 'Digital text layer'
        OCR = 'OCR', 'Printed OCR (Tesseract)'
        HANDWRITING = 'HANDWRITING', 'Handwriting recognition'

    version = models.ForeignKey(DocumentVersion, on_delete=models.CASCADE, related_name='pages')
    number = models.PositiveIntegerField()
    text = models.TextField(blank=True)
    source = models.CharField(max_length=12, choices=Source.choices, default=Source.DIGITAL)
    ocr_confidence = models.FloatField(null=True, blank=True)

    class Meta:
        unique_together = ('version', 'number')
        ordering = ['version', 'number']


class Chunk(models.Model):
    """A structure-aware piece of text (a clause / section) used for retrieval."""
    version = models.ForeignKey(DocumentVersion, on_delete=models.CASCADE, related_name='chunks')
    sequence = models.PositiveIntegerField()
    section_path = models.CharField(max_length=500, blank=True)
    heading = models.CharField(max_length=300, blank=True)
    text = models.TextField()
    page_start = models.PositiveIntegerField(default=1)
    page_end = models.PositiveIntegerField(default=1)
    clause_label = models.CharField(max_length=80, blank=True)
    clause_confidence = models.FloatField(null=True, blank=True)
    embedding = VectorField(dimensions=384, null=True, blank=True)
    search_vector = SearchVectorField(null=True, blank=True)

    class Meta:
        ordering = ['version', 'sequence']
        indexes = [
            HnswIndex(name='chunk_embedding_hnsw', fields=['embedding'], m=16, ef_construction=64,
                      opclasses=['vector_cosine_ops']),
            GinIndex(name='chunk_search_gin', fields=['search_vector']),
        ]


class RecordField(models.Model):
    """One structured fact extracted from a record (e.g. signed_date = 2025-03-12)."""

    class Status(models.TextChoices):
        AUTO = 'AUTO', 'Extracted automatically'
        NEEDS_REVIEW = 'NEEDS_REVIEW', 'Needs human review'
        VERIFIED = 'VERIFIED', 'Verified by a person'
        CORRECTED = 'CORRECTED', 'Corrected by a person'

    version = models.ForeignKey(DocumentVersion, on_delete=models.CASCADE, related_name='fields')
    key = models.CharField(max_length=40)
    label = models.CharField(max_length=80)
    value_text = models.TextField(blank=True)
    value_date = models.DateField(null=True, blank=True)
    value_number = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    confidence = models.FloatField(default=0.0)
    source_page = models.PositiveIntegerField(null=True, blank=True)
    source_quote = models.TextField(blank=True)
    grounded = models.BooleanField(default=False, help_text='The quoted evidence was found in the page text.')
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.AUTO)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('version', 'key')
        ordering = ['version', 'id']

    def __str__(self):
        return f'{self.key}={self.value_text}'


class FieldEdit(models.Model):
    """History type 3: every human change to an extracted field."""
    field = models.ForeignKey(RecordField, on_delete=models.CASCADE, related_name='edits')
    old_value = models.TextField(blank=True)
    new_value = models.TextField(blank=True)
    old_status = models.CharField(max_length=12)
    new_status = models.CharField(max_length=12)
    reason = models.CharField(max_length=300, blank=True)
    edited_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    edited_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-edited_at']


class ProcessingJob(models.Model):
    """Database-backed job queue (works on Windows without Redis/Celery)."""

    class Status(models.TextChoices):
        QUEUED = 'QUEUED'
        RUNNING = 'RUNNING'
        DONE = 'DONE'
        FAILED = 'FAILED'

    version = models.ForeignKey(DocumentVersion, on_delete=models.CASCADE, related_name='jobs')
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.QUEUED, db_index=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['created_at']
