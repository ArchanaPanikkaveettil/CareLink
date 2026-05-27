import os
import django
from django.utils import timezone

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'CareLink.settings')
django.setup()

from apps.assignments.models import CareTask

print("Cleaning up duplicate tasks on April 1st...")
assignment_id = 2
target_date = timezone.datetime(2026, 4, 1).date()

# Titles that were affected
titles = [
    "Food & Medicine (Breakfast)",
    "Bath & Personal Hygiene",
    "Physiotherapy Session"
]

for title in titles:
    # Get all tasks with this title on April 1st
    tasks_on_day = CareTask.objects.filter(
        assignment_id=assignment_id,
        title__icontains=title,
        due_date__year=2026,
        due_date__month=4,
        due_date__day=1
    ).order_by('-id') # Newest first
    
    if tasks_on_day.count() > 1:
        # Try to keep one that is 'pending', else keep the first one
        keep_task = None
        for t in tasks_on_day:
            if t.status == 'pending':
                keep_task = t
                break
        
        if not keep_task:
            keep_task = tasks_on_day.first()
            
        # Delete the others
        for t in tasks_on_day:
            if t.id != keep_task.id:
                print(f"Deleting duplicate {t.title} (ID: {t.id}, Status: {t.status})")
                t.delete()

print("Cleanup complete.")
