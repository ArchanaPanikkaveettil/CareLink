from apps.Chat.models import ChatSession, ChatMessage
from apps.Notifications.models import Notification
from django.contrib.auth import get_user_model

User = get_user_model()
admin = User.objects.get(username="admin")
user = User.objects.get(username="akhila@gmail.com")
session = ChatSession.objects.get(user=user)

# Create a new message as admin
ChatMessage.objects.create(
    session=session,
    sender=admin,
    message="This is a fresh unread message from admin"
)

# Create the notification
Notification.objects.create(
    recipient=user,
    sender=admin,
    notification_type="chat_message",
    title="New Support Message",
    message="Admin: This is a fresh unread message from admin...",
    icon="comment-dots",
    link="/chat/"
)

print("Created fresh unread message and notification for Akhila")
