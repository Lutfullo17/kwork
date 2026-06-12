import random
from django.core.mail import send_mail
from django.conf import settings


def generate_code():
    return str(random.randint(100000, 999999))


def send_email_code(user):
    from .models import Emailcode

    Emailcode.objects.filter(user=user, is_activated=False).delete()

    code = generate_code()
    Emailcode.objects.create(user=user, code=code)

    send_mail(
        subject='Tasdiqlash kodi',
        message=f'Sizning tasdiqlash kodingiz: {code}\nKod 5 daqiqa davomida amal qiladi.',
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=False,
    )