import os
import django
import sys
from datetime import date, timedelta

# Set up Django environment
sys.path.append(r'e:\Eldercare\CareLink')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'CareLink.settings')
django.setup()

from apps.Users.models import User, ElderProfile
from apps.Requests.models import CareRequest

def create_request():
    akhila = User.objects.filter(first_name__icontains='Akhila').first()
    ammini = ElderProfile.objects.filter(name__icontains='Ammini').first()

    if not akhila:
        print("Error: Akhila not found")
        return
    if not ammini:
        print("Error: Ammini Amma not found")
        return

    print(f"Creating request for Family: {akhila.get_full_name()} (ID: {akhila.id})")
    print(f"For Elder: {ammini.name} (ID: {ammini.id})")

    # Create the CareRequest
    req = CareRequest(
        family=akhila,
        elder_profile=ammini,
        patient_name=ammini.name,
        patient_age=ammini.age,
        patient_gender=ammini.gender,
        medical_condition=ammini.medical_conditions or "General age-related care",
        mobility_status=ammini.mobility_status,
        cognitive_status=ammini.cognitive_status,
        care_type="full_time",
        urgency_level="medium",
        required_skills="Elder care, Basic nursing, Medication management",
        salary_offered=25000,
        payment_frequency="monthly",
        shift_timing="Full Day (Live-in preferred)",
        start_date=date.today() + timedelta(days=2),
        duration_days=30,
        address="123 Care Street, Near Central Park",
        city="Kochi",
        state="Kerala",
        pincode="682001",
        status="open"
    )
    req.save()
    print(f"Success! Created request {req.request_id}")

if __name__ == "__main__":
    create_request()
