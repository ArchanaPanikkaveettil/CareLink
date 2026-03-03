# apps/Notifications/views.py
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from .models import Notification
from django.template.loader import render_to_string
from django.http import JsonResponse

@login_required
def all_notifications(request):
    """View for displaying all notifications"""
    notifications = Notification.objects.filter(
        recipient=request.user
    ).order_by('-created_at')
    
    context = {
        'notifications': notifications
    }
    return render(request, 'notifications/all.html', context)

@login_required
@require_POST
def mark_all_read(request):
    """Mark all notifications as read"""
    Notification.objects.filter(
        recipient=request.user,
        is_read=False
    ).update(is_read=True)
    return JsonResponse({'success': True})

@login_required
@require_POST
def mark_notification_read(request, notification_id):
    """Mark a single notification as read"""
    notification = get_object_or_404(
        Notification,
        id=notification_id,
        recipient=request.user
    )
    notification.is_read = True
    notification.save()
    return JsonResponse({'success': True})


@login_required
def get_notifications_ajax(request):
    """Return notifications HTML for dropdown"""
    notifications = Notification.objects.filter(
        recipient=request.user
    ).order_by('-created_at')[:10]  # Limit to 10 for dropdown
    
    unread_count = Notification.objects.filter(
        recipient=request.user,
        is_read=False
    ).count()
    
    html = render_to_string('notifications/dropdown.html', {
        'notifications': notifications
    }, request)
    
    return JsonResponse({
        'html': html,
        'count': unread_count
    })