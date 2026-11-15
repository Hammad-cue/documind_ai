from django.contrib import admin

from .models import Chunk, Document, DocumentVersion, FieldEdit, Page, ProcessingJob, RecordField


class VersionInline(admin.TabularInline):
    model = DocumentVersion
    extra = 0
    fields = ('number', 'original_filename', 'status', 'page_count', 'uploaded_by', 'uploaded_at')
    readonly_fields = fields


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ('title', 'organization', 'kind', 'doc_type', 'access_level', 'department', 'is_archived', 'updated_at')
    list_filter = ('organization', 'kind', 'access_level', 'is_archived')
    search_fields = ('title', 'doc_type')
    inlines = [VersionInline]


@admin.register(DocumentVersion)
class VersionAdmin(admin.ModelAdmin):
    list_display = ('document', 'number', 'status', 'file_type', 'page_count', 'uploaded_at')
    list_filter = ('status', 'file_type')


@admin.register(RecordField)
class RecordFieldAdmin(admin.ModelAdmin):
    list_display = ('version', 'key', 'value_text', 'confidence', 'grounded', 'status')
    list_filter = ('status', 'key', 'grounded')


admin.site.register([Page, Chunk, FieldEdit, ProcessingJob])
