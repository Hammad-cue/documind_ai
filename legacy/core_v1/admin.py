from django.contrib import admin
from .models import Document, DocumentChunk, Conversation, Message

# Registering models with some basic display configurations
@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ('title', 'owner', 'file_type', 'uploaded_at')
    list_filter = ('file_type', 'ocr_needed')
    search_fields = ('title', 'owner__username')

@admin.register(DocumentChunk)
class DocumentChunkAdmin(admin.ModelAdmin):
    list_display = ('document', 'sequence_number')
    search_fields = ('document__title',)

@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'created_at')

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('conversation', 'created_at')