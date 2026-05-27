import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'CareLink.settings')
django.setup()

from apps.assignments.models import CareTask

task = CareTask.objects.filter(assignment_id=2, title__icontains='Breakfast', due_date__year=2026, due_date__month=4, due_date__day=1).first()
if task:
    task.status = 'pending'
    task.save()
    print('Fixed status to pending')
else:
    print('Task not found')
