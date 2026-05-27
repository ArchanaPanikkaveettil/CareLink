from django.db import models
from django.conf import settings

class ChatSession(models.Model):
    """
    A chat session between a regular user (family/caretaker) and the admin team.
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='chat_session',
        help_text="The regular user involved in this chat with admins"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Chat with {self.user.username}"

    class Meta:
        ordering = ['-updated_at']

class ChatMessage(models.Model):
    session = models.ForeignKey(
        ChatSession, 
        on_delete=models.CASCADE, 
        related_name='messages'
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='sent_chat_messages'
    )
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Message from {self.sender.username} at {self.created_at}"

    class Meta:
        ordering = ['created_at']
