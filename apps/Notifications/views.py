from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.contrib import messages
from .models import Notification

@login_required
def get_notifications(request):
    """Get recent notifications for the current user"""
    notifications = Notification.objects.filter(
        recipient=request.user,
        is_read=False
    )[:5]
    
    return render(request, 'includes/notifications.html', {
        'notifications': notifications
    })

@login_required
def notification_count(request):
    """Get unread notification count for the current user"""
    count = Notification.objects.filter(
        recipient=request.user,
        is_read=False
    ).count()
    
    return JsonResponse({'count': count})

@login_required
def mark_notification_read(request, notification_id):
    """Mark a notification as read"""
    notification = get_object_or_404(
        Notification, 
        id=notification_id, 
        recipient=request.user
    )
    notification.mark_as_read()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': True})
    
    return redirect(request.META.get('HTTP_REFERER', 'dashboard'))

@login_required
def mark_all_notifications_read(request):
    """Mark all notifications as read"""
    Notification.objects.filter(
        recipient=request.user,
        is_read=False
    ).update(is_read=True)
    
    messages.success(request, 'All notifications marked as read.')
    return redirect(request.META.get('HTTP_REFERER', 'dashboard'))

@login_required
def all_notifications(request):
    """View all notifications"""
    notifications = Notification.objects.filter(
        recipient=request.user
    ).order_by('-created_at')
    
    # Mark all as read when viewing the full page
    notifications.filter(is_read=False).update(is_read=True)
    
    return render(request, 'notifications/all.html', {
        'notifications': notifications
    })