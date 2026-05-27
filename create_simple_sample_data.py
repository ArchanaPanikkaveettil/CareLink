#!/usr/bin/env python
"""
Simple script to create sample Kerala family and caretaker data for CareLink testing
"""
import os
import django
from decimal import Decimal

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'CareLink.settings')
django.setup()

from django.contrib.auth import get_user_model
from apps.Users.models import FamilyProfile, CaretakerProfile

User = get_user_model()

def create_sample_family():
    """Create a sample Kerala family"""
    print("Creating Kerala family...")
    
    # Create family user
    family_user = User.objects.create_user(
        username='nair_family',
        email='nair.family@example.com',
        password='family123',
        first_name='Ravi',
        last_name='Nair',
        role='family',
        phone='+919876543210',
        is_active=True
    )
    
    # Create family profile
    family_profile = FamilyProfile.objects.create(
        user=family_user,
        address='House No. 12, Kaloor-Kadavanthra Road, Kochi',
        city='Kochi',
        state='Kerala',
        pincode='682017',
        family_head='Ravi Nair',
        family_size=4,
        elderly_count=2,
        elderly_details='Mother: Lakshmi Nair (72 years) - Diabetes, Arthritis\nFather: Gopal Nair (75 years) - Hypertension, Mobility issues',
        care_requirements='Daily assistance, medication management, physiotherapy',
        preferred_languages='Malayalam, English, Tamil',
        budget_range=Decimal('15000.00'),
        care_duration='Full-time (24/7)',
        special_needs='Wheelchair accessible, diabetic care expertise',
        emergency_contact='+919876543211',
        relationship_to_elderly='Son'
    )
    
    print(f"✅ Created family: {family_user.get_full_name()} - Kochi, Kerala")
    return family_user

def create_sample_caretakers():
    """Create 2 sample caretakers from Kerala"""
    caretakers = []
    
    # Caretaker 1: Experienced female caretaker
    print("Creating caretaker 1...")
    caretaker1_user = User.objects.create_user(
        username='priya_caretaker',
        email='priya.care@example.com',
        password='caretaker123',
        first_name='Priya',
        last_name='Menon',
        role='caretaker',
        phone='+919876543212',
        is_active=True
    )
    
    caretaker1_profile = CaretakerProfile.objects.create(
        user=caretaker1_user,
        age=35,
        gender='Female',
        address='Tavarakara House, Vyttila, Kochi',
        city='Kochi',
        state='Kerala',
        pincode='682019',
        qualification='B.Sc Nursing',
        experience_years=8,
        about='Experienced nurse specializing in elderly care. Services: medication management, personal care, mobility assistance, companionship, meal preparation.',
        languages_known='Malayalam, English, Hindi, Tamil',
        expected_salary=Decimal('18000.00'),
        availability_status='available',
        aadhaar_number='123456789012',
        police_verification=True,
        medical_fitness=True
    )
    
    caretakers.append(caretaker1_user)
    print(f"✅ Created caretaker 1: {caretaker1_user.get_full_name()} - Kochi, Kerala")
    
    # Caretaker 2: Male caretaker with physiotherapy background
    print("Creating caretaker 2...")
    caretaker2_user = User.objects.create_user(
        username='arun_caretaker',
        email='arun.care@example.com',
        password='caretaker123',
        first_name='Arun',
        last_name='Pillai',
        role='caretaker',
        phone='+919876543213',
        is_active=True
    )
    
    caretaker2_profile = CaretakerProfile.objects.create(
        user=caretaker2_user,
        age=42,
        gender='Male',
        address='Sree Narayana Nagar, Thiruvananthapuram',
        city='Thiruvananthapuram',
        state='Kerala',
        pincode='695018',
        qualification='Diploma in Physiotherapy',
        experience_years=12,
        about='Physiotherapist turned caretaker with extensive experience in rehabilitation and elderly mobility care. Services: physiotherapy, mobility assistance, personal care, exercise assistance, emergency response.',
        languages_known='Malayalam, English',
        expected_salary=Decimal('20000.00'),
        availability_status='available',
        aadhaar_number='987654321098',
        police_verification=True,
        medical_fitness=True
    )
    
    caretakers.append(caretaker2_user)
    print(f"✅ Created caretaker 2: {caretaker2_user.get_full_name()} - Thiruvananthapuram, Kerala")
    
    return caretakers

def main():
    print("🌴 Creating Kerala Sample Data for CareLink 🌴")
    print("=" * 50)
    
    try:
        # Create family
        family = create_sample_family()
        
        # Create caretakers
        caretakers = create_sample_caretakers()
        
        print("\n" + "=" * 50)
        print("✅ Sample data created successfully!")
        print("\nLogin Credentials:")
        print(f"\n🏠 Family Account:")
        print(f"   Username: {family.username}")
        print(f"   Password: family123")
        print(f"   Location: Kochi, Kerala")
        print(f"   Elderly: Mother (72) & Father (75)")
        print(f"   Budget: ₹15,000/month")
        
        for i, caretaker in enumerate(caretakers, 1):
            print(f"\n👨‍⚕️ Caretaker {i}:")
            print(f"   Username: {caretaker.username}")
            print(f"   Password: caretaker123")
            if i == 1:
                print(f"   Location: Kochi, Kerala")
                print(f"   Specialty: Nursing, 8 years experience")
                print(f"   Expected Salary: ₹18,000/month")
            else:
                print(f"   Location: Thiruvananthapuram, Kerala")
                print(f"   Specialty: Physiotherapy, 12 years experience")
                print(f"   Expected Salary: ₹20,000/month")
        
        print(f"\n🎯 Ready for testing!")
        print(f"📝 Use these credentials to test family and caretaker registrations")
        
    except Exception as e:
        print(f"❌ Error creating sample data: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
