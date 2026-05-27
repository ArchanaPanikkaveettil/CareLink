from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from .models import ChatSession, ChatMessage
from django.db.models import Q
from django.contrib.auth import get_user_model
from django.contrib.messages.storage import default_storage
from apps.Notifications.models import Notification

User = get_user_model()


@login_required
def user_chat(request):
    """
    Chat view for regular users (family/caretaker) to communicate with admins.
    """
    if request.user.role == "admin":
        return redirect("admin_chat_list")

    # Clear all Django flash messages from the session
    storage = default_storage(request)
    for message in storage:
        pass  # This marks all messages as used
    del storage

    session, created = ChatSession.objects.get_or_create(user=request.user)
    
    if created:
        # Notify all admins about the new chat session
        admins = User.objects.filter(role="admin")
        for admin in admins:
            Notification.objects.create(
                recipient=admin,
                sender=request.user,
                notification_type="new_chat",
                title="New Chat Session",
                message=f"{request.user.get_full_name() or request.user.username} started a new chat session.",
                icon="comments",
                link="/chat/admin/"
            )

    messages = session.messages.all()

    # Mark messages from admin as read
    session.messages.filter(sender__role="admin", is_read=False).update(is_read=True)

    base_template = "users/family_base.html"
    if request.user.role == "caretaker":
        base_template = "users/nurse_base.html"

    context = {
        "session": session,
        "chat_messages": messages,
        "base_template": base_template,
    }
    return render(request, "chat/user_chat.html", context)


@login_required
def admin_chat_list(request):
    """
    Dashboard for admins to see all active chats.
    """
    if request.user.role != "admin":
        return redirect("user_chat")

    sessions = ChatSession.objects.all().select_related("user")

    # Calculate unread counts for each session
    for session in sessions:
        session.unread_count = session.messages.filter(
            sender=session.user, is_read=False
        ).count()

    # Calculate statistics
    family_sessions_count = sessions.filter(user__role="family").count()
    caretaker_sessions_count = sessions.filter(user__role="caretaker").count()
    total_unread_count = sum(session.unread_count for session in sessions)

    context = {
        "sessions": sessions,
        "family_sessions_count": family_sessions_count,
        "caretaker_sessions_count": caretaker_sessions_count,
        "total_unread_count": total_unread_count,
        "active_menu": "chat",
    }
    return render(request, "chat/admin_chat_list.html", context)


@login_required
def admin_chat_detail(request, session_id):
    """
    Admin view for a specific chat session with a user.
    """
    if request.user.role != "admin":
        return redirect("user_chat")

    session = get_object_or_404(ChatSession, id=session_id)
    messages = session.messages.all()

    # Mark messages from user as read
    session.messages.filter(sender=session.user, is_read=False).update(is_read=True)

    context = {"session": session, "chat_messages": messages, "active_menu": "chat"}
    return render(request, "chat/admin_chat_detail.html", context)


@login_required
def send_message(request, session_id):
    """
    AJAX endpoint to send a message.
    """
    if request.method == "POST":
        session = get_object_or_404(ChatSession, id=session_id)
        content = request.POST.get("message")

        if content:
            message = ChatMessage.objects.create(
                session=session, sender=request.user, message=content
            )

            # Create notifications
            if request.user.role == "admin":
                # Notify the user
                Notification.objects.create(
                    recipient=session.user,
                    sender=request.user,
                    notification_type="chat_message",
                    title="New Support Message",
                    message=f"Admin: {content[:50]}...",
                    icon="comment-dots",
                    link="/chat/"
                )
            else:
                # Notify all admins
                admins = User.objects.filter(role="admin")
                for admin in admins:
                    # Skip if admin is current user (unlikely here but good practice)
                    if admin == request.user: continue
                    
                    Notification.objects.create(
                        recipient=admin,
                        sender=request.user,
                        notification_type="chat_message",
                        title="New Message from User",
                        message=f"{request.user.get_full_name() or request.user.username}: {content[:50]}...",
                        icon="comment-dots",
                        link=f"/chat/admin/{session.id}/"
                    )

            # Update session's updated_at timestamp
            session.save()

            return JsonResponse(
                {
                    "status": "success",
                    "message": {
                        "content": message.message,
                        "sender": message.sender.username,
                        "timestamp": message.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                        "is_admin": message.sender.role == "admin",
                    },
                }
            )

    return JsonResponse({"status": "error"}, status=400)
