from django.db import models
from django.contrib.auth.models import User
from pgvector.django import VectorField
from django.db.models.signals import post_save
from django.dispatch import receiver

class Document(models.Model):
    FILE_TYPES = (
        ('PDF', 'PDF'),
        ('DOCX', 'DOCX'),
        ('IMAGE', 'Image'),
    )
    
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='documents')
    title = models.CharField(max_length=255)
    file = models.FileField(upload_to='documents/')
    file_type = models.CharField(max_length=10, choices=FILE_TYPES)
    ocr_needed = models.BooleanField(default=False)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    extracted_dates = models.JSONField(null=True, blank=True)
    extracted_type = models.CharField(max_length=100, null=True, blank=True) 
    extracted_summary = models.TextField(null=True, blank=True)

    def __str__(self):
        return self.title

class DocumentChunk(models.Model):
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='chunks')
    content_text = models.TextField()
    sequence_number = models.IntegerField()
   # Changed from 1536 to 384 for our free local model
    embedding = VectorField(dimensions=384, null=True, blank=True) 

    def __str__(self):
        return f"{self.document.title} - Chunk {self.sequence_number}"

class Conversation(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='conversations')
    title = models.CharField(max_length=255, blank=True)
    context_summary = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    documents = models.ManyToManyField(Document, related_name='conversations', blank=True)

    def __str__(self):
        return self.title or f"Conversation {self.id}"


    
class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)
    job_title = models.CharField(max_length=100, null=True, blank=True)

    def __str__(self):
        return f"{self.user.username}'s Profile"

# SIGNAL: Automatically create a UserProfile when a new User is registered
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)    

class Message(models.Model):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')
    user_query = models.TextField()
    response_text = models.TextField()
    
    # This is the new field we added for citations!
    sources = models.JSONField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Message in {self.conversation.title}"