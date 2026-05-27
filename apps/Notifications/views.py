# apps/Notifications/views.py
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.template.loader import render_to_string
from django.utils import timezone  # Add this for timestamp
from .models import Notification



@login_required
def all_notifications(request):
    """View for displaying all notifications"""
    notifications = Notification.objects.filter(recipient=request.user).order_by(
        "-created_at"
    )

    base_template = "users/family_base.html"
    if request.user.role == "admin":
        base_template = "admin/admin_base.html"
    elif request.user.role == "caretaker":
        base_template = "users/nurse_base.html"

    context = {"notifications": notifications, "base_template": base_template}
    return render(request, "notifications/all.html", context)


@login_required
@require_POST
def mark_all_read(request):
    """Mark all notifications as read and also mark unread chat messages as read"""
    # Mark all notifications as read
    updated_count = Notification.objects.filter(
        recipient=request.user, is_read=False
    ).update(
        is_read=True, read_at=timezone.now()
    )

    # Also mark chat messages as read to satisfy user requirement
    try:
        from apps.Chat.models import ChatMessage, ChatSession
        if request.user.role == "admin":
            # For admins, mark all messages from regular users as read
            ChatMessage.objects.filter(is_read=False).exclude(sender__role="admin").update(is_read=True)
        else:
            # For regular users, mark all messages from admins in their session as read
            try:
                session = ChatSession.objects.get(user=request.user)
                session.messages.filter(sender__role="admin", is_read=False).update(is_read=True)
            except ChatSession.DoesNotExist:
                pass
    except ImportError:
        pass

    return JsonResponse(
        {
            "status": "success",
            "message": f"Marked {updated_count} notifications as read",
            "count": 0,
        }
    )


@login_required
@require_POST  # Add this decorator
def mark_notification_read(request, notification_id):
    """Mark a single notification as read"""
    notification = get_object_or_404(
        Notification, id=notification_id, recipient=request.user
    )

    if not notification.is_read:
        notification.is_read = True
        notification.read_at = timezone.now()  # Add timestamp
        notification.save()

    # Get updated unread count
    unread_count = Notification.objects.filter(
        recipient=request.user, is_read=False
    ).count()

    return JsonResponse(
        {
            "status": "success",
            "message": "Notification marked as read",
            "count": unread_count,
        }
    )


@login_required
def get_notifications_ajax(request):
    """Return notifications HTML for dropdown"""
    try:
        # Get latest 10 notifications for dropdown
        notifications = Notification.objects.filter(recipient=request.user).order_by(
            "-created_at"
        )[:10]

        # Get total unread count for badge
        unread_count = Notification.objects.filter(
            recipient=request.user, is_read=False
        ).count()

        # Render dropdown HTML
        html = render_to_string(
            "notifications/dropdown.html",
            {"notifications": notifications, "unread_count": unread_count},
            request,
        )

        return JsonResponse({"status": "success", "html": html, "count": unread_count})

    except Exception as e:
        # Log error if needed
        print(f"Error loading notifications: {e}")
        return JsonResponse(
            {
                "status": "error",
                "html": '<div class="no-notifications"><i class="fas fa-exclamation-circle"></i><p>Error loading notifications</p></div>',
                "count": 0,
            }
        )


@login_required
def get_notification_count(request):
    """Return unread notification count for AJAX"""
    count = Notification.objects.filter(recipient=request.user, is_read=False).count()

    return JsonResponse({"status": "success", "count": count})


@login_required
@require_POST
def delete_all_notifications(request):
    """Delete all notifications for the current user"""
    try:
        count = Notification.objects.filter(recipient=request.user).count()
        Notification.objects.filter(recipient=request.user).delete()
        return JsonResponse(
            {
                "status": "success",
                "message": f"Deleted {count} notifications",
                "count": 0,
            }
        )
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=400)


@login_required
@require_POST
def delete_read_notifications(request):
    """Delete only read notifications"""
    try:
        count = Notification.objects.filter(
            recipient=request.user, is_read=True
        ).count()
        Notification.objects.filter(recipient=request.user, is_read=True).delete()
        return JsonResponse(
            {
                "status": "success",
                "message": f"Deleted {count} read notifications",
                "count": Notification.objects.filter(
                    recipient=request.user, is_read=False
                ).count(),
            }
        )
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=400)


@login_required
@require_POST
def delete_notification(request, notification_id):
    """Delete a specific notification"""
    try:
        notification = get_object_or_404(
            Notification, id=notification_id, recipient=request.user
        )
        notification.delete()
        return JsonResponse(
            {
                "status": "success",
                "message": "Notification deleted",
                "count": Notification.objects.filter(
                    recipient=request.user, is_read=False
                ).count(),
            }
        )
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=400)
