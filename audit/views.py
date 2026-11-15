from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import CanViewAudit

from .models import AuditEvent


class AuditListView(APIView):
    permission_classes = [CanViewAudit]

    def get(self, request):
        p = request.query_params
        qs = AuditEvent.objects.filter(organization_id=request.user.membership.organization_id)
        if p.get('action'):
            qs = qs.filter(action=p['action'])
        if p.get('actor'):
            qs = qs.filter(actor_name__icontains=p['actor'])
        if p.get('target_type'):
            qs = qs.filter(target_type=p['target_type'])
        if p.get('target_id'):
            qs = qs.filter(target_id=p['target_id'])
        if p.get('date_from'):
            qs = qs.filter(created_at__date__gte=p['date_from'])
        if p.get('date_to'):
            qs = qs.filter(created_at__date__lte=p['date_to'])
        try:
            limit = min(int(p.get('limit', 50)), 200)
            offset = max(int(p.get('offset', 0)), 0)
        except ValueError:
            limit, offset = 50, 0
        total = qs.count()
        rows = [{'id': e.id, 'created_at': e.created_at, 'actor': e.actor_name, 'action': e.action,
                 'target_type': e.target_type, 'target_id': e.target_id, 'target_label': e.target_label,
                 'metadata': e.metadata, 'ip_address': e.ip_address}
                for e in qs[offset:offset + limit]]
        return Response({'count': total, 'results': rows, 'actions': AuditEvent.Action.values})
