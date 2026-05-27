from apps.Chat.models import ChatMessage

# Delete all chat messages that contain "Message from" in their content
deleted_count = ChatMessage.objects.filter(message__icontains="Message from").delete()[0]
print(f"Deleted {deleted_count} messages containing 'Message from'")
