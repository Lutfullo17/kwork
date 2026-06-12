
"""
Celery task'lari — vaqtni nazorat qilish va avtomatik status o'zgartirish.
settings.py da: CELERY_BEAT_SCHEDULE ga qo'shish kerak.
"""
from celery import shared_task
from django.utils import timezone
from datetime import timedelta


def run_check_deadlines():
    """
    - Muddati 1 soatdan kam qolgan loyihalarga ogohlantirish yuboradi.
    - Muddati o'tgan loyihalarni DELAYED qiladi.
    """
    from marketplace.models import Order
    from .services import notify_deadline_soon, notify_deadline_passed

    now = timezone.now()
    one_hour_later = now + timedelta(hours=1)

    soon_orders = Order.objects.filter(
        status=Order.Status.IN_PROGRESS,
        deadline__lte=one_hour_later,
        deadline__gt=now,
    ).select_related('assigned_freelancer')

    for order in soon_orders:
        if order.assigned_freelancer:
            notify_deadline_soon(
                freelancer=order.assigned_freelancer,
                order_title=order.title,
                order_pk=order.pk,
            )

    delayed_orders = Order.objects.filter(
        status=Order.Status.IN_PROGRESS,
        deadline__lt=now,
    ).select_related('assigned_freelancer')

    for order in delayed_orders:
        order.status = Order.Status.DELAYED
        order.save(update_fields=['status'])
        if order.assigned_freelancer:
            notify_deadline_passed(
                freelancer=order.assigned_freelancer,
                order_title=order.title,
                order_pk=order.pk,
            )


@shared_task
def check_deadlines():
    """Celery task — har 10 daqiqada ishlaydi."""
    run_check_deadlines()
