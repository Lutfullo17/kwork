from django.contrib import admin
from django.urls import path,include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls')),
    path('', include('marketplace.urls')),
    path('notifications/', include('notifications.urls', namespace='notifications')),
    path('chat/', include('chat.urls', namespace='chat')),
    path('reviews/', include('reviews.urls', namespace='reviews')),
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)