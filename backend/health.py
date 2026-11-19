"""GET /api/health/ - used by the Docker health check. Plain Django view: no login, no rate limit."""
from django.db import connection
from django.http import JsonResponse


def health(request):
    try:
        with connection.cursor() as cur:
            cur.execute('SELECT 1')
        return JsonResponse({'status': 'ok', 'database': 'ok'})
    except Exception as exc:
        return JsonResponse({'status': 'error', 'database': str(exc)[:200]}, status=503)
