import os
import django
from django.utils import timezone

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'CareLink.settings')
django.setup()

from django.contrib.auth import get_user_model
User = get_user_model()
from apps.Users.models import CaretakerProfile, ElderProfile
from apps.Requests.models import CareRequest

def create_users():
    # Delete existing test users first
    User.objects.filter(username__in=['test_family', 'test_nurse']).delete()

    print("Creating Test Family...")
    family, created = User.objects.get_or_create(
        username="test_family",
        defaults={
            "email": "family@test.com",
            "first_name": "Test",
            "last_name": "Family",
            "role": "family",
            "is_active": True,
            "phone": "9876543210"
        }
    )
    if created:
        family.set_password("password123")
        family.save()
        print(f"✅ Created family user: {family.username} (Password: password123)")
    else:
        print(f"ℹ️ Family user {family.username} already exists.")

    print("Creating an Open CareRequest for the family...")
    req, r_created = CareRequest.objects.get_or_create(
        family=family,
        patient_name="Martha Stewart (Test)",
        defaults={
            "patient_age": 75,
            "patient_gender": "female",
            "medical_condition": "Post-surgery recovery",
            "mobility_status": "walker",
            "cognitive_status": "normal",
            "care_type": "part_time",
            "urgency_level": "high",
            "required_skills": "Wound Care, Vitals Monitoring",
            "salary_offered": 800.00,
            "payment_frequency": "hourly",
            "shift_timing": "5 PM to 9 PM",
            "start_date": timezone.now().date(),
            "duration_days": 14,
            "address": "123 Family Lane",
            "city": "Kochi",
            "state": "Kerala",
            "pincode": "682001",
            "status": "open",
            "interview_required": True,
            "interview_type": "phone"
        }
    )
    if r_created:
        print(f"✅ Created Open CareRequest for patient '{req.patient_name}'. (Required for pre-booking)")
    else:
        print(f"ℹ️ Open CareRequest for patient '{req.patient_name}' already exists.")

    print("\nCreating Test Nurse...")
    nurse, created = User.objects.get_or_create(
        username="test_nurse",
        defaults={
            "email": "nurse@test.com",
            "first_name": "Elena",
            "last_name": "Gilbert",
            "role": "caretaker",
            "is_active": True,
            "is_verified": True,
            "phone": "9876543211"
        }
    )
    if created:
        nurse.set_password("password123")
        nurse.save()
        print(f"✅ Created nurse user: {nurse.username} (Password: password123)")
        
        CaretakerProfile.objects.create(
            user=nurse,
            experience_years=4,
            qualification="BSc Nursing",
            skills="First Aid, BP Monitoring, Diabetic Care",
            city="Kochi",
            state="Kerala",
            address="456 Nurse Avenue"
        )
        print("✅ Created verified CaretakerProfile for the test nurse.")
    else:
        print(f"ℹ️ Nurse user {nurse.username} already exists.")

if __name__ == "__main__":
    create_users()
