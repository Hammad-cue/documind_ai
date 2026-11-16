from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsOrgMember

from .models import Notification


def _payload(n):
    return {'id': n.id, 'kind': n.kind, 'title': n.title, 'body': n.body, 'link': n.link,
            'document_id': n.document_id, 'created_at': n.created_at, 'read': n.read_at is not None}


class NotificationListView(APIView):
    permission_classes = [IsOrgMember]

    def get(self, request):
        qs = Notification.objects.filter(recipient=request.user)
        return Response({'unread': qs.filter(read_at__isnull=True).count(),
                         'results': [_payload(n) for n in qs[:50]]})


class NotificationReadView(APIView):
    """POST {"ids": [1, 2]} marks those as read; POST {} marks everything as read."""
    permission_classes = [IsOrgMember]

    def post(self, request):
        qs = Notification.objects.filter(recipient=request.user, read_at__isnull=True)
        ids = request.data.get('ids')
        if ids:
            qs = qs.filter(id__in=ids)
        updated = qs.update(read_at=timezone.now())
        return Response({'marked': updated})
