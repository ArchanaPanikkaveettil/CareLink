# apps/Notifications/context_processors.py (if it exists, update it or delete it)
from .models import Notification


def notification_count(request):
    if request.user.is_authenticated:
        unread_count = Notification.objects.filter(
            recipient=request.user, is_read=False
        ).count()
        return {"unread_notifications_count": unread_count}
    return {"unread_notifications_count": 0}
