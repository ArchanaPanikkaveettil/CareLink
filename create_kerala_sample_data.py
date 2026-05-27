#!/usr/bin/env python
"""
Script to create sample Kerala family and caretaker data for CareLink testing
"""
import os
import django
from decimal import Decimal
from datetime import date

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'CareLink.settings')
django.setup()

from django.contrib.auth import get_user_model
from apps.Users.models import FamilyProfile, CaretakerProfile, ElderProfile

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
    
    # Create elderly profiles first
    mother = ElderProfile.objects.create(
        first_name='Lakshmi',
        last_name='Nair',
        gender='female',
        date_of_birth=date(1952, 5, 15),  # 72 years old
        medical_conditions='Diabetes, Arthritis',
        special_needs='Daily medication, mobility assistance',
        dietary_requirements='Diabetic diet, low salt',
        emergency_contact='+919876543210',
        relationship='Mother'
    )
    
    father = ElderProfile.objects.create(
        first_name='Gopal',
        last_name='Nair',
        gender='male',
        date_of_birth=date(1949, 8, 22),  # 75 years old
        medical_conditions='Hypertension, Mobility issues',
        special_needs='Blood pressure monitoring, wheelchair assistance',
        dietary_requirements='Low sodium diet',
        emergency_contact='+919876543210',
        relationship='Father'
    )
    
    # Create family profile
    family_profile = FamilyProfile.objects.create(
        user=family_user,
        family_type='nuclear',
        family_size=4,
        phone='+919876543210',
        emergency_contact='+919876543211',
        address='House No. 12, Kaloor-Kadavanthra Road, Kochi',
        city='Kochi',
        state='Kerala',
        pincode='682017',
        country='India',
        residence_type='independent',
        accessibility_requirements='Wheelchair accessible, grab bars in bathroom',
        pets_at_home=False,
        smokers_in_home=False,
        preferred_caretaker_gender='female',
        previous_caretaker=False
    )
    
    # Add elders to family
    family_profile.elders.add(mother, father)
    
    print(f"✅ Created family: {family_user.get_full_name()} - Kochi, Kerala")
    print(f"   Elders: Mother (72) & Father (75)")
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
        date_of_birth=date(1989, 3, 10),  # 35 years old
        gender='female',
        emergency_contact_name='Anil Menon',
        emergency_contact_phone='+919876543213',
        address='Tavarakara House, Vyttila, Kochi',
        city='Kochi',
        state='Kerala',
        pincode='682019',
        country='India',
        availability_status='available',
        employment_type='full_time',
        experience_level='senior',
        expected_salary=Decimal('18000.00'),
        about='Experienced nurse specializing in elderly care. Services: medication management, personal care, mobility assistance, companionship, meal preparation.',
        languages_known='Malayalam, English, Hindi, Tamil',
        qualification='B.Sc Nursing',
        skills='Medication management, personal care, mobility assistance, companionship',
        previous_employers='Kochi Medical Center (2016-2020)',
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
        date_of_birth=date(1982, 7, 25),  # 42 years old
        gender='male',
        emergency_contact_name='Sunita Pillai',
        emergency_contact_phone='+919876543214',
        address='Sree Narayana Nagar, Thiruvananthapuram',
        city='Thiruvananthapuram',
        state='Kerala',
        pincode='695018',
        country='India',
        availability_status='available',
        employment_type='full_time',
        experience_level='expert',
        expected_salary=Decimal('20000.00'),
        about='Physiotherapist turned caretaker with extensive experience in rehabilitation and elderly mobility care. Services: physiotherapy, mobility assistance, personal care, exercise assistance.',
        languages_known='Malayalam, English',
        qualification='Diploma in Physiotherapy',
        skills='Physiotherapy, mobility assistance, personal care, exercise assistance',
        previous_employers='Trivandrum Rehabilitation Center (2012-2024)',
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
        print("\n🔐 Login Credentials:")
        print(f"\n🏠 Family Account:")
        print(f"   Username: {family.username}")
        print(f"   Password: family123")
        print(f"   Location: Kochi, Kerala")
        print(f"   Family Size: 4 members")
        print(f"   Elderly: Mother (72) & Father (75)")
        print(f"   Address: House No. 12, Kaloor-Kadavanthra Road, Kochi")
        
        for i, caretaker in enumerate(caretakers, 1):
            print(f"\n👨‍⚕️ Caretaker {i}:")
            print(f"   Username: {caretaker.username}")
            print(f"   Password: caretaker123")
            if i == 1:
                print(f"   Location: Kochi, Kerala")
                print(f"   Age: 35 years")
                print(f"   Qualification: B.Sc Nursing")
                print(f"   Experience: 8 years (Senior Level)")
                print(f"   Expected Salary: ₹18,000/month")
                print(f"   Languages: Malayalam, English, Hindi, Tamil")
            else:
                print(f"   Location: Thiruvananthapuram, Kerala")
                print(f"   Age: 42 years")
                print(f"   Qualification: Diploma in Physiotherapy")
                print(f"   Experience: 12 years (Expert Level)")
                print(f"   Expected Salary: ₹20,000/month")
                print(f"   Languages: Malayalam, English")
        
        print(f"\n🎯 Ready for testing!")
        print(f"📝 Use these credentials to test:")
        print(f"   • Family registration and login")
        print(f"   • Caretaker registration and login")
        print(f"   • Search and matching functionality")
        print(f"   • Chat support system")
        
    except Exception as e:
        print(f"❌ Error creating sample data: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
