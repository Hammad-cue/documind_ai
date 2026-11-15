import os
from turtle import title

from rest_framework import status
from rest_framework.generics import ListCreateAPIView, RetrieveDestroyAPIView, CreateAPIView, RetrieveUpdateAPIView
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.contrib.auth.models import User
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from .models import Document, Conversation, Message, UserProfile
from .serializers import DocumentSerializer, MessageSerializer, UserProfileSerializer
from .utils import process_document, generate_rag_response


# 1. SECURED: Registration Serializer & View
class UserRegistrationSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('username', 'password')
        extra_kwargs = {'password': {'write_only': True}}

    def create(self, validated_data):
        user = User.objects.create_user(**validated_data)
        return user

class RegisterView(CreateAPIView):
    queryset = User.objects.all()
    permission_classes = (AllowAny,) # Anyone can access the sign-up page
    serializer_class = UserRegistrationSerializer

class UserProfileView(RetrieveUpdateAPIView):
    serializer_class = UserProfileSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = (MultiPartParser, FormParser) # Required to accept image uploads

    def get_object(self):
        # get_or_create ensures that users created BEFORE we added the signal still get a profile!
        profile, created = UserProfile.objects.get_or_create(user=self.request.user)
        return profile    


# 2. SECURED: Document Upload View
class DocumentUploadView(ListCreateAPIView): 
    serializer_class = DocumentSerializer
    parser_classes = (MultiPartParser, FormParser)
    permission_classes = [IsAuthenticated] # LOCKED!

    # Only show documents belonging to the logged-in user
    def get_queryset(self):
        return Document.objects.filter(owner=self.request.user)

    def perform_create(self, serializer):
        # 1. Strict File Type Validation
        file_obj = self.request.data.get('file')
        if file_obj:
            ext = os.path.splitext(file_obj.name)[1].lower()
            allowed_exts = ['.pdf', '.docx', '.png', '.jpg', '.jpeg']
            if ext not in allowed_exts:
                raise ValidationError({"detail": f"Security Block: File type '{ext}' is not supported."})

        # 2. Duplicate Title Validation
        title = self.request.data.get('title')
        if Document.objects.filter(owner=self.request.user, title=title).exists():
            raise ValidationError({"detail": f"A document named '{title}' is already in your vault."})

        # 3. Save the document and apply the custom tag if provided
        custom_tag = self.request.data.get('custom_tag', '').strip()
        document = serializer.save(owner=self.request.user)
        
        if custom_tag:
            document.extracted_type = custom_tag
            document.save()

        # 4. Send to background processing
        process_document(document)


# 3. SECURED: Chat View
class ChatQueryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        conv_id = request.query_params.get('conversation_id')
        
        if conv_id:
            try:
                conversation = Conversation.objects.get(id=conv_id, user=request.user)
                messages = Message.objects.filter(conversation=conversation).order_by('id')
                doc_ids = list(conversation.documents.values_list('id', flat=True))
                
                # NEW: We now include the 'sources' array when loading chat history
                data = {
                    "document_ids": doc_ids,
                    "messages": [
                        {
                            "user": msg.user_query, 
                            "ai": msg.response_text,
                            "sources": msg.sources or [] # Pass sources to frontend
                        } 
                        for msg in messages
                    ]
                }
                return Response(data, status=status.HTTP_200_OK)
            except Conversation.DoesNotExist:
                return Response({"error": "Conversation not found"}, status=status.HTTP_404_NOT_FOUND)
        
        return Response({"error": "No conversation id provided"}, status=status.HTTP_400_BAD_REQUEST)

    def post(self, request, *args, **kwargs):
        user_query = request.data.get('user_query')
        conversation_id = request.data.get('conversation_id')
        document_ids = request.data.get('document_ids', []) 
        user = request.user 

        if not user_query:
            return Response({"error": "user_query is required"}, status=status.HTTP_400_BAD_REQUEST)

        if conversation_id:
            conversation = Conversation.objects.get(id=conversation_id, user=user)
        else:
            title = user_query[:50] if len(user_query) > 50 else user_query
            conversation = Conversation.objects.create(user=user, title=title)

        if document_ids:
            conversation.documents.add(*document_ids)

        # 1. CRITICAL FIX: Unpack the tuple returned by generate_rag_response
        ai_response_text, sources_list = generate_rag_response(user_query, conversation, document_ids)

        # 2. CRITICAL FIX: Save the new sources list to the database
        message = Message.objects.create(
            conversation=conversation,
            user_query=user_query,
            response_text=ai_response_text,
            sources=sources_list
        )

        # 3. Return the text AND sources back to the Vue frontend
        return Response({
            "conversation_id": conversation.id,
            "response_text": message.response_text,
            "sources": message.sources,
        }, status=status.HTTP_200_OK)

# 2. NEW: Endpoint to delete conversations
class ConversationDeleteView(APIView):
    permission_classes = [IsAuthenticated]
    
    def delete(self, request, pk):
        try:
            conversation = Conversation.objects.get(id=pk, user=request.user)
            conversation.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Conversation.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)


# 4. SECURED: Delete Document View
class DocumentDetailView(RetrieveDestroyAPIView):
    serializer_class = DocumentSerializer
    permission_classes = [IsAuthenticated] # LOCKED!
    
    # Ensure a user can't maliciously delete someone else's document by guessing the ID
    def get_queryset(self):
        return Document.objects.filter(owner=self.request.user)
    
class ConversationListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Fetch all conversations for this user, ordered newest first
        conversations = Conversation.objects.filter(user=request.user).order_by('-created_at')
        data = [{"id": c.id, "title": c.title} for c in conversations]
        return Response(data, status=status.HTTP_200_OK)    