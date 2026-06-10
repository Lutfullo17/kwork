from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator

from marketplace.models import Order


class Review(models.Model):
    order      = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='review')
    reviewer   = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='given_reviews')
    freelancer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='received_reviews')
    stars      = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    comment    = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self._update_freelancer_rating()

    def _update_freelancer_rating(self):
        from django.db.models import Avg
        from accounts.models import Profile
        profile, _ = Profile.objects.get_or_create(user=self.freelancer)
        reviews = Review.objects.filter(freelancer=self.freelancer)
        avg     = reviews.aggregate(Avg('stars'))['stars__avg'] or 0
        profile.rating               = round(avg, 2)
        profile.completed_jobs_count = reviews.count()
        profile.save(update_fields=['rating', 'completed_jobs_count'])
        profile.update_level()

    def __str__(self):
        return f"{self.stars}⭐ - {self.freelancer}"