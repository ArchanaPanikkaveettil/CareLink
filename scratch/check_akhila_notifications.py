from apps.Notifications.models import Notification
from django.contrib.auth import get_user_model

User = get_user_model()
user = User.objects.get(username="akhila@gmail.com")

unread = Notification.objects.filter(recipient=user, is_read=False)
read = Notification.objects.filter(recipient=user, is_read=True)

print(f"User: {user.username}")
print(f"Unread notifications: {unread.count()}")
for n in unread:
    print(f"  - [UNREAD] {n.title}: {n.message}")

print(f"Read notifications: {read.count()}")
for n in read:
    print(f"  - [READ] {n.title}: {n.message}")
