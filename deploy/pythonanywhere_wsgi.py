"""
PythonAnywhere Web tab → WSGI configuration file ichiga nusxa qiling.

1. YOUR_USERNAME ni o'z login'ingiz bilan almashtiring
2. Loyiha yo'lini tekshiring (masalan /home/YOUR_USERNAME/kwork)
"""

import os
import sys

PROJECT_PATH = '/home/YOUR_USERNAME/kwork'

if PROJECT_PATH not in sys.path:
    sys.path.insert(0, PROJECT_PATH)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

from dotenv import load_dotenv

load_dotenv(os.path.join(PROJECT_PATH, '.env'))

from django.core.wsgi import get_wsgi_application

application = get_wsgi_application()
