from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from .views import DocumentUploadView, ChatQueryView, DocumentDetailView, RegisterView, ConversationListView, ConversationDeleteView, UserProfileView

urlpatterns = [
    # Authentication Endpoints
    path('register/', RegisterView.as_view(), name='register'),
    
    # CRITICAL FIX: Changed 'login/' to 'token/' so the Vue frontend can find it!
    path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # Existing Endpoints
    path('profile/', UserProfileView.as_view(), name='user-profile'),
    path('upload/', DocumentUploadView.as_view(), name='document-upload'),
    path('upload/<int:pk>/', DocumentDetailView.as_view(), name='document-detail'),
    path('chat/', ChatQueryView.as_view(), name='chat-query'),
    path('conversations/', ConversationListView.as_view(), name='conversation-list'),
    path('conversations/<int:pk>/', ConversationDeleteView.as_view(), name='conversation-delete'),
]