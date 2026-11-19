import json
import time

from django.http import StreamingHttpResponse
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


def _parse_ask(request):
    """Validate an ask request. Returns (error_response, text, doc_ids, conversation, history)."""
    text = (request.data.get('query') or '').strip()
    if not text:
        return Response({'query': 'Ask something.'}, status=400), None, None, None, None
    if len(text) > 2000:
        return Response({'query': 'Question is too long (max 2000 characters).'}, status=400), None, None, None, None
    try:
        doc_ids = [int(i) for i in (request.data.get('document_ids') or [])]
    except (TypeError, ValueError):
        return Response({'document_ids': 'Must be a list of ids.'}, status=400), None, None, None, None
    m = request.user.membership
    conv_id = request.data.get('conversation_id')
    if conv_id:
        conv = get_object_or_404(Conversation, pk=conv_id, user=request.user)
    else:
        conv = Conversation.objects.create(organization=m.organization, user=request.user, title=text[:80])
    history = list(conv.queries.order_by('-created_at').values_list('text', flat=True)[:3])[::-1]
    return None, text, doc_ids, conv, history


def _save(request, conv, text, doc_ids, out, latency):
    q = Query.objects.create(conversation=conv, text=text, intent=out['intent'], plan=out['plan'],
                             scope_document_ids=doc_ids, answer=out['answer'], sources=out['sources'],
                             results=out['results'], latency_ms=latency)
    conv.save(update_fields=['updated_at'])
    record(request.user, AuditEvent.Action.SEARCH, conv, request, label=text[:200], intent=out['intent'],
           results=len(out['sources']), latency_ms=latency)
    return q


class AskView(APIView):
    permission_classes = [IsOrgMember]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'assistant'

    def post(self, request):
        error, text, doc_ids, conv, history = _parse_ask(request)
        if error:
            return error
        started = time.perf_counter()
        out = engine.answer(request.user, text, document_ids=doc_ids or None, history=history)
        q = _save(request, conv, text, doc_ids, out, int((time.perf_counter() - started) * 1000))
        return Response({'conversation_id': conv.id, **_query_payload(q)})


class AskStreamView(APIView):
    """Same as AskView, but the answer is sent as it is written: one JSON object per line
    (plan, sources, delta..., done). The question is saved to history once the answer is complete."""
    permission_classes = [IsOrgMember]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'assistant'

    def post(self, request):
        error, text, doc_ids, conv, history = _parse_ask(request)
        if error:
            return error

        def line(obj):
            return json.dumps(obj, default=str) + '\n'

        def events():
            started = time.perf_counter()
            final = None
            try:
                for event in engine.answer_events(request.user, text, document_ids=doc_ids or None, history=history):
                    if event['type'] == 'final':
                        final = event
                        continue
                    yield line(event)
            except Exception as exc:   # never leave the browser waiting on a broken stream
                yield line({'type': 'error', 'message': f'Something went wrong while answering: {exc}'[:300]})
                return
            q = _save(request, conv, text, doc_ids, final, int((time.perf_counter() - started) * 1000))
            yield line({'type': 'done', 'conversation_id': conv.id, **_query_payload(q)})

        response = StreamingHttpResponse(events(), content_type='application/x-ndjson')
        response['Cache-Control'] = 'no-cache'
        response['X-Accel-Buffering'] = 'no'      # tell nginx not to buffer the stream
        return response


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
