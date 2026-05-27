# apps/Notifications/context_processors.py (if it exists, update it or delete it)
from .models import Notification


def notification_count(request):
    """Add notification count and recent notifications to context"""
    if request.user.is_authenticated:
        try:
            unread_count = Notification.objects.filter(
                recipient=request.user,
                is_read=False
            ).count()
            # Fetch latest 10 notifications for the dropdown
            notifications = Notification.objects.filter(
                recipient=request.user
            ).order_by('-created_at')[:10]
            
            return {
                'unread_notifications_count': unread_count,
                'notifications': notifications
            }
        except Exception as e:
            return {'unread_notifications_count': 0, 'notifications': []}
    return {'unread_notifications_count': 0, 'notifications': []}
