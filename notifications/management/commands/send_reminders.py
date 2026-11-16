from django.core.management.base import BaseCommand

from notifications.service import run_reminders


class Command(BaseCommand):
    help = 'Send expiry and notice-deadline reminders (the worker also does this hourly).'

    def handle(self, *args, **opts):
        sent = run_reminders()
        self.stdout.write(self.style.SUCCESS(f'{sent} reminder(s) created.'))
