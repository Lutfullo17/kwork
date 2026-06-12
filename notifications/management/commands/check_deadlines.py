from django.core.management.base import BaseCommand

from notifications.tasks import run_check_deadlines


class Command(BaseCommand):
    help = 'Loyiha muddatlarini tekshiradi (PythonAnywhere scheduled task uchun).'

    def handle(self, *args, **options):
        run_check_deadlines()
        self.stdout.write(self.style.SUCCESS('Deadline tekshiruvi yakunlandi.'))
