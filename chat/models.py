from django.db import models
from django.utils import timezone
from django.conf import settings

from marketplace.models import Order


class ChatRoom(models.Model):
    order      = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='chat_rooms')
    client     = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='client_rooms')
    freelancer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='freelancer_rooms')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('order', 'freelancer')

    def __str__(self):
        return f"{self.order.title} | {self.freelancer}"

    @property
    def is_blocked(self):
        return self.offers.filter(status=Offer.Status.REJECTED).count() >= 3

    @property
    def active_submission(self):
        return self.submissions.filter(status=Submission.Status.PENDING).last()


class Message(models.Model):
    room       = models.ForeignKey(ChatRoom, on_delete=models.CASCADE, related_name='messages')
    sender     = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='messages')
    content    = models.TextField()
    is_read    = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.sender} - {self.content[:50]}"


class Offer(models.Model):
    class Status(models.TextChoices):
        PENDING  = 'PENDING',  'Kutilmoqda'
        ACCEPTED = 'ACCEPTED', 'Qabul qilindi'
        REJECTED = 'REJECTED', 'Rad etildi'
        EXPIRED  = 'EXPIRED',  "Muddati o'tgan"

    room           = models.ForeignKey(ChatRoom, on_delete=models.CASCADE, related_name='offers')
    sender         = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='sent_offers')
    proposed_price = models.DecimalField(max_digits=12, decimal_places=2)
    delivery_days  = models.PositiveIntegerField()
    message        = models.TextField(null=True, blank=True)
    status         = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    created_at     = models.DateTimeField(auto_now_add=True)
    responded_at   = models.DateTimeField(null=True, blank=True)

    def accept(self):
        from datetime import timedelta
        from notifications.services import notify_offer_accepted

        self.status       = self.Status.ACCEPTED
        self.responded_at = timezone.now()
        self.save(update_fields=['status', 'responded_at'])

        order                     = self.room.order
        order.status              = Order.Status.IN_PROGRESS
        order.final_price         = self.proposed_price
        order.deadline            = timezone.now() + timedelta(days=self.delivery_days)
        order.assigned_freelancer = self.sender
        order.save(update_fields=['status', 'final_price', 'deadline', 'assigned_freelancer'])

        Offer.objects.filter(
            room__order=order,
            status=self.Status.PENDING,
        ).exclude(pk=self.pk).update(status=self.Status.EXPIRED)

        notify_offer_accepted(
            freelancer  = self.sender,
            order_title = order.title,
            order_pk    = order.pk,
        )

    def reject(self):
        self.status       = self.Status.REJECTED
        self.responded_at = timezone.now()
        self.save(update_fields=['status', 'responded_at'])

    def __str__(self):
        return f"{self.proposed_price} so'm | {self.delivery_days} kun | {self.status}"


class Submission(models.Model):
    class Status(models.TextChoices):
        PENDING  = 'PENDING',  'Tekshirilmoqda'
        APPROVED = 'APPROVED', 'Tasdiqlandi'
        REJECTED = 'REJECTED', 'Qayta ishlash kerak'

    room        = models.ForeignKey(ChatRoom, on_delete=models.CASCADE, related_name='submissions')
    freelancer  = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='submissions')
    file        = models.FileField(upload_to='submissions/%Y/%m/')
    comment     = models.TextField(null=True, blank=True)
    status      = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    rating      = models.PositiveSmallIntegerField(null=True, blank=True)  # 1-5
    client_note = models.TextField(null=True, blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    def approve(self, rating, client_note=''):
        from notifications.services import notify_work_approved

        self.status      = self.Status.APPROVED
        self.rating      = rating
        self.client_note = client_note
        self.reviewed_at = timezone.now()
        self.save(update_fields=['status', 'rating', 'client_note', 'reviewed_at'])

        order        = self.room.order
        order.status = Order.Status.COMPLETED
        order.save(update_fields=['status'])

        from accounts.models import Profile
        profile, _ = Profile.objects.get_or_create(user=self.freelancer)
        profile.completed_jobs_count += 1

        # Reyting o'rtachasi hisoblanadi
        all_ratings = Submission.objects.filter(
            freelancer=self.freelancer,
            status=self.Status.APPROVED,
            rating__isnull=False
        ).values_list('rating', flat=True)

        if all_ratings:
            profile.rating = sum(all_ratings) / len(all_ratings)

        profile.save(update_fields=['rating', 'completed_jobs_count'])
        profile.update_level()

        notify_work_approved(
            freelancer  = self.freelancer,
            order_title = order.title,
            order_pk    = order.pk,
            rating      = rating,
        )

    def reject_work(self, client_note=''):
        """Mijoz qayta ishlashni so'raydi."""
        from notifications.services import notify_work_rejected

        self.status      = self.Status.REJECTED
        self.client_note = client_note
        self.reviewed_at = timezone.now()
        self.save(update_fields=['status', 'client_note', 'reviewed_at'])

        notify_work_rejected(
            freelancer  = self.freelancer,
            order_title = self.room.order.title,
            order_pk    = self.room.order.pk,
        )

    def __str__(self):
        return f"{self.freelancer} → {self.room.order.title} [{self.status}]"