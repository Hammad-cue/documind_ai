import time

from notifications.service import run_reminders

from django.core.management.base import BaseCommand

from documents.pipeline import queue


class Command(BaseCommand):
    help = 'Process uploaded documents (OCR, chunking, embeddings, record extraction).'

    def add_arguments(self, parser):
        parser.add_argument('--once', action='store_true', help='Process everything queued, then exit.')
        parser.add_argument('--poll', type=float, default=2.0, help='Seconds between polls when idle.')

    def handle(self, *args, **opts):
        n = queue.requeue_stale()
        if n:
            self.stdout.write(f'Re-queued {n} stale job(s).')
        self.stdout.write(self.style.SUCCESS('Worker started. Waiting for documents...'))
        last_reminders = 0.0
        while True:
            if time.time() - last_reminders > 3600:  # expiry / notice reminders, hourly
                last_reminders = time.time()
                try:
                    sent = run_reminders()
                    if sent:
                        self.stdout.write(f'   sent {sent} reminder(s)')
                except Exception as exc:
                    self.stdout.write(self.style.WARNING(f'   reminders failed: {exc}'))
            job = queue.claim_next()
            if job is None:
                if opts['once']:
                    return
                time.sleep(opts['poll'])
                continue
            label = f'job {job.pk} ({job.version})'
            self.stdout.write(f'-> {label}')
            started = time.perf_counter()
            job = queue.run_job(job.pk)
            secs = time.perf_counter() - started
            if job.status == 'DONE':
                self.stdout.write(self.style.SUCCESS(f'   done in {secs:.1f}s'))
            else:
                self.stdout.write(self.style.WARNING(f'   {job.status}: {job.error[:200]}'))
