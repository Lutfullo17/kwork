import os

if os.environ.get('CELERY_ENABLED', 'False').lower() in ('true', '1', 'yes'):
    from .celery import app as celery_app

    __all__ = ('celery_app',)
else:
    celery_app = None
    __all__ = ()
