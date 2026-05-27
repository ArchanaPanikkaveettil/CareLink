import os
import django
from django.utils import timezone
from datetime import timedelta, time

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'CareLink.settings')
django.setup()

from apps.assignments.models import CareAssignment, CareTask

def seed():
    try:
        assignment = CareAssignment.objects.get(id=2)
    except CareAssignment.DoesNotExist:
        print("Assignment 2 not found!")
        assignment = CareAssignment.objects.first()
        if not assignment:
            print("No assignments found!")
            return

    # Start from 2 days ago to show history
    now = timezone.now()
    start = (now - timedelta(days=2)).date()
    end = (now + timedelta(days=7)).date() # 1 week seed

    daily_tasks = [
        ("Food & Medicine (Breakfast)", time(8, 0), "high"),
        ("Bath & Personal Hygiene", time(10, 0), "medium"),
        ("Food & Medicine (Lunch)", time(13, 0), "high"),
        ("Afternoon Vitals Check", time(15, 0), "medium"),
        ("Evening Tea & Walk", time(17, 0), "low"),
        ("Food & Medicine (Dinner)", time(20, 0), "high"),
    ]

    print(f"Seeding tasks for patient: {assignment.care_request.patient_name if assignment.care_request else 'Default'}")
    
    curr = start
    count = 0
    while curr <= end:
        for title, t, priority in daily_tasks:
            dt = timezone.make_aware(timezone.datetime.combine(curr, t))
            # If it's more than 4 hours ago, mark as completed (to show history)
            # If it's recent past, leave pending for user to see 'Missed'
            status = 'completed' if dt < (now - timedelta(hours=6)) else 'pending'
            
            # Create task
            CareTask.objects.create(
                assignment=assignment,
                title=title,
                due_date=dt,
                priority=priority,
                status=status,
                assigned_by=assignment.family
            )
            count += 1
            
        # Weekly physiotherapy on Mon, Wed, Fri
        if curr.weekday() in [0, 2, 4]:
            dt = timezone.make_aware(timezone.datetime.combine(curr, time(11, 30)))
            status = 'completed' if dt < (now - timedelta(hours=6)) else 'pending'
            CareTask.objects.create(
                assignment=assignment,
                title="Physiotherapy Session",
                due_date=dt,
                priority="medium",
                status=status,
                assigned_by=assignment.family
            )
            count += 1
        curr += timedelta(days=1)

    # Specific appointments
    appt_date = (now + timedelta(days=3)).date()
    CareTask.objects.create(
        assignment=assignment,
        title="Dr. Appointment (Monthly Checkup)",
        due_date=timezone.make_aware(timezone.datetime.combine(appt_date, time(15, 30))),
        priority="high",
        status="pending",
        assigned_by=assignment.family
    )
    
    another_date = (now + timedelta(days=5)).date()
    CareTask.objects.create(
        assignment=assignment,
        title="Medicine Refill (Pharmacy)",
        due_date=timezone.make_aware(timezone.datetime.combine(another_date, time(11, 0))),
        priority="medium",
        status="pending",
        assigned_by=assignment.family
    )
    
    print(f"SUCCESS: Seeded {count + 2} tasks.")

if __name__ == "__main__":
    seed()
