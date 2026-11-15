import time

from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from accounts.permissions import IsOrgMember
from audit.models import AuditEvent
from audit.service import record

from . import engine
from .models import Conversation, Query


def _query_payload(q):
    return {'id': q.id, 'query': q.text, 'intent': q.intent, 'plan': q.plan, 'answer': q.answer,
            'sources': q.sources, 'results': q.results, 'latency_ms': q.latency_ms,
            'scope_document_ids': q.scope_document_ids, 'created_at': q.created_at}


class AskView(APIView):
    permission_classes = [IsOrgMember]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'assistant'

    def post(self, request):
        text = (request.data.get('query') or '').strip()
        if not text:
            return Response({'query': 'Ask something.'}, status=400)
        if len(text) > 2000:
            return Response({'query': 'Question is too long (max 2000 characters).'}, status=400)
        try:
            doc_ids = [int(i) for i in (request.data.get('document_ids') or [])]
        except (TypeError, ValueError):
            return Response({'document_ids': 'Must be a list of ids.'}, status=400)

        m = request.user.membership
        conv_id = request.data.get('conversation_id')
        if conv_id:
            conv = get_object_or_404(Conversation, pk=conv_id, user=request.user)
        else:
            conv = Conversation.objects.create(organization=m.organization, user=request.user, title=text[:80])
        history = list(conv.queries.order_by('-created_at').values_list('text', flat=True)[:3])[::-1]

        started = time.perf_counter()
        out = engine.answer(request.user, text, document_ids=doc_ids or None, history=history)
        latency = int((time.perf_counter() - started) * 1000)

        q = Query.objects.create(conversation=conv, text=text, intent=out['intent'], plan=out['plan'],
                                 scope_document_ids=doc_ids, answer=out['answer'], sources=out['sources'],
                                 results=out['results'], latency_ms=latency)
        conv.save(update_fields=['updated_at'])
        record(request.user, AuditEvent.Action.SEARCH, conv, request, label=text[:200], intent=out['intent'],
               results=len(out['sources']), latency_ms=latency)
        return Response({'conversation_id': conv.id, **_query_payload(q)})


class ConversationListView(APIView):
    permission_classes = [IsOrgMember]

    def get(self, request):
        convs = Conversation.objects.filter(user=request.user)[:200]
        return Response([{'id': c.id, 'title': c.title, 'updated_at': c.updated_at} for c in convs])


class ConversationDetailView(APIView):
    permission_classes = [IsOrgMember]

    def get(self, request, pk):
        conv = get_object_or_404(Conversation, pk=pk, user=request.user)
        return Response({'id': conv.id, 'title': conv.title,
                         'queries': [_query_payload(q) for q in conv.queries.all()]})

    def delete(self, request, pk):
        get_object_or_404(Conversation, pk=pk, user=request.user).delete()
        return Response(status=204)
