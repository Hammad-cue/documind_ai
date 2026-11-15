from rest_framework import serializers
from .models import Document, DocumentChunk, Conversation, Message, UserProfile


class DocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = ['id', 'title', 'file', 'file_type', 'ocr_needed', 'uploaded_at', 'extracted_dates', 'extracted_type', 'extracted_summary']
        # We make the owner read-only because we will assign it automatically in the view
        read_only_fields = ['owner']

class MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = ['id', 'conversation', 'user_query', 'response_text', 'created_at']
        read_only_fields = ['response_text'] # The AI generates this  

class UserProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    email = serializers.EmailField(source='user.email')
    first_name = serializers.CharField(source='user.first_name', allow_blank=True, required=False)
    last_name = serializers.CharField(source='user.last_name', allow_blank=True, required=False)

    class Meta:
        model = UserProfile
        fields = ('username', 'email', 'first_name', 'last_name', 'avatar', 'job_title')

    def update(self, instance, validated_data):
        # Extract the nested user data
        user_data = validated_data.pop('user', {})
        user = instance.user

        # Update base User fields
        if 'email' in user_data:
            user.email = user_data['email']
        if 'first_name' in user_data:
            user.first_name = user_data['first_name']
        if 'last_name' in user_data:
            user.last_name = user_data['last_name']
        user.save()

        # Update Profile fields
        instance.job_title = validated_data.get('job_title', instance.job_title)
        if 'avatar' in validated_data:
            instance.avatar = validated_data['avatar']
        instance.save()

        return instance         
        
             