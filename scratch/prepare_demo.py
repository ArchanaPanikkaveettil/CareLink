import os
import django
import sys
from datetime import timedelta, date, time, datetime
from django.utils import timezone
import random

# Add project root to sys.path
sys.path.append('e:/Eldercare/CareLink')

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'CareLink.settings')
django.setup()

from django.contrib.auth import get_user_model
from apps.Users.models import FamilyProfile, CaretakerProfile, ElderProfile
from apps.Requests.models import CareRequest, CareBooking
from apps.assignments.models import CareAssignment, Attendance, DailyCareReport, CareTask
from apps.Applications.models import CareApplication

User = get_user_model()

def create_demo_data():
    print("--- Cleaning and Restarting Demo Data Creation ---")
    
    # 1. Clear existing demo data to avoid conflicts
    User.objects.filter(username__in=["sharma_family", "nurse_priya"]).delete()
    
    # 1. Create Family User
    family_user, created = User.objects.get_or_create(
        username="sharma_family",
        defaults={
            "email": "sharma@example.com",
            "first_name": "Rajesh",
            "last_name": "Sharma",
            "role": "family",
            "is_verified": True,
            "phone": "9876543210"
        }
    )
    family_user.set_password("demo1234")
    family_user.save()
    
    FamilyProfile.objects.get_or_create(
        user=family_user,
        defaults={
            "family_type": "joint",
            "family_size": 4,
            "city": "Mumbai",
            "state": "Maharashtra",
            "address": "102, Silver Oaks, Bandra West",
            "verified_by_admin": True
        }
    )
    print(f"Family user created: {family_user.username}")

    # 2. Create Nurse User
    nurse_user, created = User.objects.get_or_create(
        username="nurse_priya",
        defaults={
            "email": "priya@example.com",
            "first_name": "Priya",
            "last_name": "Dhar",
            "role": "caretaker",
            "is_verified": True,
            "phone": "9123456789"
        }
    )
    nurse_user.set_password("demo1234")
    nurse_user.save()
    
    nurse_profile, _ = CaretakerProfile.objects.get_or_create(
        user=nurse_user,
        defaults={
            "experience_years": 8,
            "experience_level": "senior",
            "qualification": "B.Sc Nursing",
            "skills": "Elder Care, Medication Management, Physiotherapy Assistance, Vital Monitoring",
            "languages": "English, Hindi, Marathi",
            "bio": "Compassionate senior nurse with 8 years of experience in geriatric care. Specialized in post-surgery recovery and chronic illness management.",
            "city": "Mumbai",
            "availability_status": "busy",
            "verified_by_admin": True
        }
    )
    print(f"Nurse user created: {nurse_user.username}")

    # 3. Create Elder Profiles
    ElderProfile.objects.get_or_create(
        family=family_user,
        name="Ramesh Sharma",
        defaults={
            "age": 72,
            "gender": "male",
            "relationship": "parent",
            "blood_group": "B+",
            "medical_conditions": "Diabetes, Hypertension, Recovering from hip surgery",
            "medications": "Metformin 500mg, Amlodipine 5mg",
            "mobility_status": "walker",
            "is_primary": True
        }
    )
    
    ElderProfile.objects.get_or_create(
        family=family_user,
        name="Savitri Sharma",
        defaults={
            "age": 68,
            "gender": "female",
            "relationship": "parent",
            "medical_conditions": "Early stage Dementia",
            "mobility_status": "independent",
            "is_primary": False
        }
    )
    print("Elder profiles created.")

    # 4. Create a Care Request and Application
    today = date.today()
    start_date = today - timedelta(days=14)
    end_date = today + timedelta(days=30)
    
    care_request = CareRequest.objects.create(
        family=family_user,
        patient_name="Ramesh & Savitri Sharma",
        request_id=f"REQ-{random.randint(1000, 9999)}",
        patient_age=72,
        patient_gender="male",
        medical_condition="Diabetes, Hypertension, Recovering from hip surgery",
        care_type="full_time",
        status="closed",
        mobility_status="walker",
        salary_offered=25000,
        duration_days=30,
        hours_per_day=8,
        city="Mumbai",
        state="Maharashtra",
        start_date=start_date,
        end_date=end_date,
        urgency_level="medium"
    )
    
    application = CareApplication.objects.create(
        request=care_request,
        caretaker=nurse_user,
        status="accepted",
        proposed_rate=25000,
        message="I have extensive experience with diabetic patients and dementia care."
    )

    # 5. Create Care Assignment
    assignment = CareAssignment.objects.create(
        family=family_user,
        caretaker=nurse_user,
        care_request=care_request,
        application=application,
        start_date=start_date,
        end_date=end_date,
        status="active",
        shift_type="full_time",
        work_hours_per_day=8.0,
        monthly_salary=25000.0,
        notes="Daily monitoring of BP and Sugar is critical."
    )
    print(f"Care Assignment created, starting from {start_date}")

    # 6. Create History (Past 14 days, excluding TODAY)
    for i in range(14):  # 1 to 14 days ago
        d = today - timedelta(days=(14-i))
        
        # Attendance
        Attendance.objects.create(
            assignment=assignment,
            date=d,
            status="present",
            check_in_time=time(9, 0),
            check_out_time=time(17, 0),
            actual_hours_worked=8.0
        )
        
        # Daily Report
        DailyCareReport.objects.create(
            assignment=assignment,
            report_date=d,
            blood_pressure_systolic=random.randint(120, 135),
            blood_pressure_diastolic=random.randint(75, 85),
            heart_rate=random.randint(70, 80),
            temperature=36.6,
            blood_sugar=random.randint(110, 140),
            mood="happy" if i % 3 != 0 else "calm",
            activities_done="Morning walk in garden, Light exercises.",
            medications_given="Metformin at 9 AM, Hypertension meds at 8 PM.",
            observations="Patient is responding well to therapy. Appetite is normal."
        )
    print("History for past 2 weeks (up to yesterday) created.")

    # 7. Create TODAY'S Attendance (It's 6:30 AM, so not checked in yet)
    # We leave today's Attendance empty or non-existent so the nurse can check in.
    print("Today's record left empty for live demo check-in.")

    # 8. Create Tasks (Today and Future)
    
    # Task 1 for Today (COMPLETED) - To show "Activities Done" is working
    CareTask.objects.create(
        assignment=assignment,
        title="Morning Medicine",
        description="Give Metformin and Amlodipine after breakfast.",
        priority="high",
        due_date=timezone.now().replace(hour=8, minute=30, second=0, microsecond=0),
        status="completed",
        completed_at=timezone.now().replace(hour=8, minute=45, second=0, microsecond=0)
    )

    # Task 2 for Today (Pending)
    CareTask.objects.create(
        assignment=assignment,
        title="Check Glucose Level",
        description="Check sugar level before breakfast (Expected at 8:00 AM)",
        priority="high",
        due_date=timezone.now().replace(hour=8, minute=0, second=0, microsecond=0),
        status="pending"
    )
    
    # Task 3 for Today (Pending)
    CareTask.objects.create(
        assignment=assignment,
        title="Mid-day Vital Check",
        description="Record BP and Pulse rate.",
        priority="medium",
        due_date=timezone.now().replace(hour=13, minute=0, second=0, microsecond=0),
        status="pending"
    )

    # Future Task
    CareTask.objects.create(
        assignment=assignment,
        title="Weekly Physiotherapy Session",
        description="Conduct 45 mins of hip recovery exercises.",
        priority="high",
        due_date=timezone.now() + timedelta(days=1),
        status="pending"
    )
    
    # Past Task (Completed)
    CareTask.objects.create(
        assignment=assignment,
        title="Medicine Refill",
        description="Buy monthly stock of BP and Diabetes meds.",
        priority="medium",
        due_date=timezone.now() - timedelta(days=1),
        status="verified",
        completed_at=timezone.now() - timedelta(days=1)
    )
    print("Tasks created (1 Completed for today to show stats, others pending).")

    # 9. Create a past booking for reviews
    past_booking_date = today - timedelta(days=20)
    past_booking = CareBooking.objects.create(
        caretaker=nurse_user,
        family=family_user,
        care_request=care_request,
        booking_date=past_booking_date,
        start_time=time(10, 0),
        end_time=time(14, 0),
        duration_hours=4,
        status="completed",
        completed_at=timezone.now() - timedelta(days=20)
    )
    
    from apps.Users.models import CaretakerReview
    CaretakerReview.objects.create(
        booking=past_booking,
        caretaker=nurse_profile,
        family=family_user.family_profile,
        rating=5,
        comment="Priya is excellent! She was very patient with my father and handled his medications perfectly."
    )
    print("Past booking and review created.")

    print("\n--- Demo Data Fixed Successfully ---")
    print(f"Current System Time: {timezone.now()}")
    print(f"Family Username: sharma_family / Password: demo1234")
    print(f"Nurse Username: nurse_priya / Password: demo1234")

if __name__ == "__main__":
    create_demo_data()
