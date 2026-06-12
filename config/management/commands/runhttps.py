from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand
from werkzeug.serving import make_ssl_devcert


class Command(BaseCommand):
    help = 'Run the development server over HTTPS (self-signed certificate).'

    def add_arguments(self, parser):
        parser.add_argument(
            'addrport',
            nargs='?',
            default='127.0.0.1:8000',
            help='Optional IP address and port (default: 127.0.0.1:8000)',
        )

    def handle(self, *args, **options):
        certs_dir = Path(settings.BASE_DIR) / 'certs'
        certs_dir.mkdir(exist_ok=True)
        cert_base = certs_dir / 'dev'

        if not cert_base.with_suffix('.crt').exists() or not cert_base.with_suffix('.key').exists():
            self.stdout.write('Generating self-signed SSL certificate...')
            make_ssl_devcert(str(cert_base), host='localhost')

        cert_file = str(cert_base.with_suffix('.crt'))
        key_file = str(cert_base.with_suffix('.key'))

        self.stdout.write(self.style.SUCCESS(
            f'Starting HTTPS server at https://{options["addrport"]}/'
        ))
        self.stdout.write(
            'Browser may warn about the certificate — accept it for local development.'
        )

        call_command(
            'runserver_plus',
            options['addrport'],
            cert_file=cert_file,
            key_file=key_file,
        )
