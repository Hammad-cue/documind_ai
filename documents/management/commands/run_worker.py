import time

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
        while True:
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
