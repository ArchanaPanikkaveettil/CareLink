import os
import django
from django.utils import timezone

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'CareLink.settings')
django.setup()

from apps.assignments.models import CareTask

print("Finding and fixing shifted tasks...")
assignment_id = 2
tasks = CareTask.objects.filter(assignment_id=assignment_id)

for task in tasks:
    if "Breakfast" in task.title and task.due_date.year == 2026 and task.due_date.month in [3, 4]:
        dt = timezone.datetime(2026, 4, 1, 8, 0)
        task.due_date = timezone.make_aware(dt)
        task.save()
        print(f"Restored: {task.title} -> {task.due_date}")
        
    elif "Hygiene" in task.title and task.due_date.year == 2026 and task.due_date.month in [3, 4]:
        dt = timezone.datetime(2026, 4, 1, 10, 0)
        task.due_date = timezone.make_aware(dt)
        task.save()
        print(f"Restored: {task.title} -> {task.due_date}")
        
    elif "Physiotherapy" in task.title and task.due_date.year == 2026 and task.due_date.month in [3, 4]:
        dt = timezone.datetime(2026, 4, 1, 11, 30)
        task.due_date = timezone.make_aware(dt)
        task.save()
        print(f"Restored: {task.title} -> {task.due_date}")

print("Fix complete.")
