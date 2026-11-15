from datetime import timedelta

from django.utils import timezone

from .models import AuditEvent


def _client_ip(request):
    if request is None:
        return None
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def record(user, action, target=None, request=None, label=None, **metadata):
    """Write one audit event. Never raises: auditing must not break the request."""
    membership = getattr(user, 'membership', None)
    if membership is None:
        return None
    target_id = str(getattr(target, 'pk', '') or '') if target is not None else ''
    if action == AuditEvent.Action.VIEW:
        # opening a document fetches metadata + file (+ re-renders); log one VIEW per minute per person
        recent = timezone.now() - timedelta(seconds=60)
        if AuditEvent.objects.filter(actor=user, action=action, target_id=target_id,
                                     target_type=target.__class__.__name__ if target is not None else '',
                                     created_at__gte=recent).exists():
            return None
    try:
        return AuditEvent.objects.create(
            organization=membership.organization,
            actor=user,
            actor_name=user.get_username(),
            action=action,
            target_type=target.__class__.__name__ if target is not None else '',
            target_id=target_id,
            target_label=(label or (str(target) if target is not None else ''))[:300],
            metadata=metadata,
            ip_address=_client_ip(request),
        )
    except Exception as exc:  # pragma: no cover
        print(f'[audit] failed to record {action}: {exc}')
        return None
