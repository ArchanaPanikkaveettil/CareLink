from .models import ChatMessage, ChatSession

def chat_context(request):
    """Add unread chat message count to all templates"""
    if request.user.is_authenticated:
        if request.user.role == "admin":
            # For admins, count messages from all users that are unread
            count = ChatMessage.objects.filter(
                is_read=False
            ).exclude(sender__role="admin").count()
            return {"total_unread_chat_count": count}
        else:
            # For regular users, count messages from admins in their session
            try:
                session = ChatSession.objects.get(user=request.user)
                count = session.messages.filter(
                    sender__role="admin", 
                    is_read=False
                ).count()
                return {"unread_chat_count": count}
            except ChatSession.DoesNotExist:
                return {"unread_chat_count": 0}
    return {}
