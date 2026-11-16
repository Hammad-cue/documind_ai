from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from accounts.views import DepartmentViewSet, LoginView, MemberViewSet, MeView, RegisterOrganizationView
from assistant.views import AskView, ConversationDetailView, ConversationListView
from audit.views import AuditListView
from notifications.views import NotificationListView, NotificationReadView
from documents.views import (DocumentViewSet, FieldCreateView, FieldHistoryView, FieldView, RecordListView,
                             ReviewQueueView)

router = DefaultRouter()
router.register('documents', DocumentViewSet, basename='document')
router.register('org/departments', DepartmentViewSet, basename='department')
router.register('org/members', MemberViewSet, basename='member')

urlpatterns = [
    path('admin/', admin.site.urls),
    # auth
    path('api/auth/register-organization/', RegisterOrganizationView.as_view()),
    path('api/auth/token/', LoginView.as_view()),
    path('api/auth/token/refresh/', TokenRefreshView.as_view()),
    path('api/auth/me/', MeView.as_view()),
    # records
    path('api/records/', RecordListView.as_view()),
    path('api/records/review-queue/', ReviewQueueView.as_view()),
    path('api/records/fields/', FieldCreateView.as_view()),
    path('api/records/fields/<int:pk>/', FieldView.as_view()),
    path('api/records/fields/<int:pk>/history/', FieldHistoryView.as_view()),
    # assistant
    path('api/assistant/ask/', AskView.as_view()),
    path('api/assistant/conversations/', ConversationListView.as_view()),
    path('api/assistant/conversations/<int:pk>/', ConversationDetailView.as_view()),
    # audit
    path('api/audit/', AuditListView.as_view()),
    # notifications
    path('api/notifications/', NotificationListView.as_view()),
    path('api/notifications/read/', NotificationReadView.as_view()),
    path('api/', include(router.urls)),
]

# Only avatars are public. Documents are served through /api/documents/<id>/file/ with permission checks.
if settings.DEBUG:
    urlpatterns += static('/media/avatars/', document_root=settings.MEDIA_ROOT / 'avatars')
