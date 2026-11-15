"""
A tiny database-backed job queue.

Upload views call enqueue(); the worker (`python manage.py run_worker`) claims jobs with
SELECT ... FOR UPDATE SKIP LOCKED, so several workers can run safely in parallel.
"""
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from documents.models import ProcessingJob

MAX_ATTEMPTS = 3


def enqueue(version):
    job = ProcessingJob.objects.create(version=version)
    if settings.PROCESS_INLINE:
        run_job(job.pk)
    return job


def claim_next():
    with transaction.atomic():
        job = (ProcessingJob.objects.select_for_update(skip_locked=True)
               .filter(status=ProcessingJob.Status.QUEUED).order_by('created_at').first())
        if job is None:
            return None
        job.status = ProcessingJob.Status.RUNNING
        job.started_at = timezone.now()
        job.attempts += 1
        job.save(update_fields=['status', 'started_at', 'attempts'])
        return job


def run_job(job_id):
    from .runner import process_version
    job = ProcessingJob.objects.get(pk=job_id)
    try:
        process_version(job.version_id)
        job.status = ProcessingJob.Status.DONE
        job.error = ''
    except Exception as exc:
        job.error = str(exc)[:2000]
        retryable = 'No readable text' not in job.error and 'limit is' not in job.error
        job.status = ProcessingJob.Status.QUEUED if retryable and job.attempts < MAX_ATTEMPTS else ProcessingJob.Status.FAILED
    job.finished_at = timezone.now()
    job.save(update_fields=['status', 'error', 'finished_at'])
    return job


def requeue_stale(minutes=30):
    cutoff = timezone.now() - timedelta(minutes=minutes)
    return ProcessingJob.objects.filter(status=ProcessingJob.Status.RUNNING, started_at__lt=cutoff) \
        .update(status=ProcessingJob.Status.QUEUED)
