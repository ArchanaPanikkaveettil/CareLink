from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, get_user_model
from django.db.models import Q
from django.utils import timezone
from .models import User, CaretakerProfile, FamilyProfile, CaretakerAvailability

User = get_user_model()


# -------------------------------------------------------------------------
# Home / Landing Page
# -------------------------------------------------------------------------

def index(request):
    return render(request, "users/index.html")


# -------------------------------------------------------------------------
# Caretaker Registration
# -------------------------------------------------------------------------

def caretaker_register(request):
    if request.method == "POST":
        try:
            # ========== ACCOUNT DETAILS ==========
            username = request.POST.get("username")
            email = request.POST.get("email")
            first_name = request.POST.get("first_name")
            last_name = request.POST.get("last_name")
            password = request.POST.get("password")
            confirm_password = request.POST.get("confirm_password")
            phone = request.POST.get("phone")  # This goes to User model
            
            # Basic validation
            if not all([username, email, first_name, last_name, password, confirm_password, phone]):
                messages.error(request, "All account fields are required.")
                return redirect("caretaker_register")
            
            if password != confirm_password:
                messages.error(request, "Passwords do not match.")
                return redirect("caretaker_register")
            
            if len(password) < 6:
                messages.error(request, "Password must be at least 6 characters.")
                return redirect("caretaker_register")
            
            # Check if username/email exists
            if User.objects.filter(username=username).exists() or User.objects.filter(email=email).exists():
                messages.error(request, "Username or email already exists.")
                return redirect("caretaker_register")
            
            # ========== VERIFICATION FIELDS ==========
            date_of_birth = request.POST.get("date_of_birth")
            gender = request.POST.get("gender")
            
            # Professional verification documents
            certificate = request.FILES.get("certificate")
            identity_proof = request.FILES.get("identity_proof")
            qualification = request.POST.get("qualification")
            experience_years = request.POST.get("experience_years")
            
            # Address for background verification
            address = request.POST.get("address")
            city = request.POST.get("city")
            state = request.POST.get("state")
            pincode = request.POST.get("pincode")
            
            # Emergency contact
            emergency_name = request.POST.get("emergency_name")
            emergency_phone = request.POST.get("emergency_phone")
            emergency_relation = request.POST.get("emergency_relation")
            
            # ========== VALIDATE VERIFICATION FIELDS ==========
            if not all([date_of_birth, gender, certificate, identity_proof, 
                       qualification, experience_years, address, city, state, pincode,
                       emergency_name, emergency_phone, emergency_relation]):
                messages.error(request, "All verification fields are required for security purposes.")
                return redirect("caretaker_register")
            
            # Terms acceptance
            accepted_terms = request.POST.get("accepted_terms") == "on"
            if not accepted_terms:
                messages.error(request, "You must accept the Terms and Conditions.")
                return redirect("caretaker_register")
            
            # Create user (phone goes in User model)
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                role="caretaker",
                is_verified=False,
                verification_status="pending",
                phone=phone,  # This is in User model
                accepted_terms=accepted_terms,
                accepted_terms_date=timezone.now()
            )
            
            # Create caretaker profile (NO phone field here)
            profile = CaretakerProfile.objects.create(
                user=user,
                # Emergency contact
                emergency_contact_name=emergency_name,
                emergency_contact_phone=emergency_phone,
                emergency_contact_relation=emergency_relation,
                
                # Personal
                date_of_birth=date_of_birth,
                gender=gender,
                
                # Professional
                experience_years=experience_years,
                qualification=qualification,
                certificate=certificate,
                identity_proof=identity_proof,
                
                # Location
                address=address,
                city=city,
                state=state,
                pincode=pincode,
                country="India",
                
                # Default values
                skills="",
                languages="",
                bio="",
                availability_status="available",
                verified_by_admin=False
            )
            
            messages.success(request, "Registration successful! Your documents are under verification. You'll be notified once verified.")
            return redirect("login")
            
        except Exception as e:
            messages.error(request, f"Registration failed: {str(e)}")
            return redirect("caretaker_register")
    
    return render(request, "users/caretaker_register.html")


# -------------------------------------------------------------------------
# Family Registration
# -------------------------------------------------------------------------

def family_register(request):
    if request.method == "POST":
        try:
            # Get only essential registration data
            first_name = request.POST.get("first_name")
            last_name = request.POST.get("last_name")
            email = request.POST.get("email")
            password = request.POST.get("password")
            confirm_password = request.POST.get("confirm_password")
            phone = request.POST.get("phone")
            
            # Basic validation
            if not all([first_name, last_name, email, password, confirm_password, phone]):
                messages.error(request, "All fields are required.")
                return redirect("family_register")
            
            # Password validation
            if password != confirm_password:
                messages.error(request, "Passwords do not match.")
                return redirect("family_register")
            
            if len(password) < 6:
                messages.error(request, "Password must be at least 6 characters long.")
                return redirect("family_register")
            
            # Check if email already exists
            if User.objects.filter(username=email).exists():
                messages.error(request, "Email already registered. Please use another email or login.")
                return redirect("family_register")
            
            # Terms acceptance
            accepted_terms = request.POST.get("accepted_terms") == "on"
            if not accepted_terms:
                messages.error(request, "You must accept the Terms and Conditions.")
                return redirect("family_register")
            
            # Create user (auto-verified)
            user = User.objects.create_user(
                username=email,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                role="family",
                is_verified=True,
                phone=phone,
                accepted_terms=accepted_terms,
                accepted_terms_date=timezone.now()
            )
            
            # Create basic family profile (only essential fields)
            FamilyProfile.objects.create(
                user=user,
                phone=phone,
                # Add minimal required fields with defaults
                address="",  # Will be filled later
                patient_name="",  # Will be filled later
                patient_age=None,  # Will be filled later
                primary_medical_condition="",  # Will be filled later
                care_required="",  # Will be filled later
            )
            
            messages.success(
                request, 
                "Registration successful! You can now login. Please complete your profile after login."
            )
            return redirect("login")
            
        except Exception as e:
            messages.error(request, f"Registration failed: {str(e)}")
            return redirect("family_register")
    
    return render(request, "users/family_register.html")


# -------------------------------------------------------------------------
# Custom Login (Role-Based Redirection)
# -------------------------------------------------------------------------

def custom_login(request):
    # Clear any existing messages before processing login
    storage = messages.get_messages(request)
    storage.used = True
    
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

        if not username or not password:
            messages.error(request, "Please enter both username and password.")
            return render(request, "users/login.html")

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            
            # Clear messages again before redirect to prevent them from showing on next page
            storage = messages.get_messages(request)
            storage.used = True

            if user.role == "admin":
                return redirect("/admin/")

            elif user.role == "family":
                # Add welcome message that will ONLY show on dashboard
                messages.success(request, f"Welcome back, {user.email}!")
                return redirect("family_dashboard")

            elif user.role == "caretaker":
                # Check BOTH is_verified and verification_status
                if user.is_verified and user.verification_status == "verified":
                    messages.success(request, f"Welcome back, {user.first_name}!")
                    return redirect("caretaker_dashboard")
                else:
                    return redirect("verification_pending")
        else:
            messages.error(request, "Invalid username or password.")

    return render(request, "users/login.html")


# -------------------------------------------------------------------------
# Caretaker Profile Views
# -------------------------------------------------------------------------

@login_required
def caretaker_profile(request):
    if request.user.role != 'caretaker':
        messages.error(request, "Access denied. This page is for caretakers only.")
        return redirect('index')
    
    try:
        profile = request.user.caretaker_profile
        
        # Process skills and languages for template
        skills_list = []
        if profile.skills:
            skills_list = [skill.strip() for skill in profile.skills.split(',') if skill.strip()]
        
        languages_list = []
        if profile.languages:
            languages_list = [lang.strip() for lang in profile.languages.split(',') if lang.strip()]
            
    except CaretakerProfile.DoesNotExist:
        profile = CaretakerProfile.objects.create(
            user=request.user,
            address=""  # Remove phone from here
        )
        skills_list = []
        languages_list = []
        messages.info(request, "Please complete your profile information.")
    
    # Get availability schedule
    availability = profile.availability_schedule.all().order_by('day_of_week')
    
    context = {
        'profile': profile,
        'user': request.user,  # Pass user to access phone
        'availability': availability,
        'skills_list': skills_list,
        'languages_list': languages_list
    }
    return render(request, 'users/caretaker_profile.html', context)


# -------------------------------------------------------------------------
# Caretaker Profile Update View
# -------------------------------------------------------------------------

@login_required
def update_caretaker_profile(request):
    """Update caretaker profile with detailed information"""
    if request.user.role != 'caretaker':
        messages.error(request, "Access denied.")
        return redirect('index')
    
    # Get or create profile
    try:
        profile = request.user.caretaker_profile
    except CaretakerProfile.DoesNotExist:
        profile = CaretakerProfile.objects.create(
            user=request.user
            # Remove phone from here
        )
    
    if request.method == "POST":
        try:
            # ========== PERSONAL INFORMATION ==========
            date_of_birth = request.POST.get("date_of_birth")
            if date_of_birth:
                profile.date_of_birth = date_of_birth
            
            profile.gender = request.POST.get("gender", profile.gender)
            
            # ========== CONTACT INFORMATION ==========
            # Update User model's phone field (NOT profile)
            request.user.phone = request.POST.get("phone", request.user.phone)
            
            # Emergency contact (these ARE in CaretakerProfile)
            profile.emergency_contact_name = request.POST.get("emergency_contact_name", "")
            profile.emergency_contact_phone = request.POST.get("emergency_contact_phone", "")
            profile.emergency_contact_relation = request.POST.get("emergency_contact_relation", "")
            
            # ========== PROFESSIONAL INFORMATION ==========
            experience_years = request.POST.get("experience_years")
            if experience_years:
                profile.experience_years = int(experience_years)
            
            profile.experience_level = request.POST.get("experience_level", "entry")
            profile.qualification = request.POST.get("qualification", "")
            profile.specialized_training = request.POST.get("specialized_training", "")
            
            # Skills and languages
            profile.skills = request.POST.get("skills", "")
            profile.languages = request.POST.get("languages", "")
            profile.employment_type = request.POST.get("employment_type", "full_time")
            
            # ========== PROFESSIONAL SUMMARY ==========
            profile.bio = request.POST.get("bio", "")
            profile.achievements = request.POST.get("achievements", "")
            
            # ========== AVAILABILITY ==========
            profile.availability_status = request.POST.get("availability_status", "available")
            profile.preferred_shift = request.POST.get("preferred_shift", "flexible")
            profile.willing_to_relocate = request.POST.get("willing_to_relocate") == "on"
            
            max_distance = request.POST.get("max_travel_distance")
            if max_distance:
                profile.max_travel_distance = int(max_distance)
            
            # ========== LOCATION ==========
            profile.address = request.POST.get("address", "")
            profile.city = request.POST.get("city", "")
            profile.state = request.POST.get("state", "")
            profile.country = request.POST.get("country", "India")
            profile.pincode = request.POST.get("pincode", "")
            
            # ========== DOCUMENTS (Optional updates) ==========
            if 'resume' in request.FILES:
                profile.resume = request.FILES['resume']
            if 'background_check' in request.FILES:
                profile.background_check = request.FILES['background_check']
            if 'profile_picture' in request.FILES:
                request.user.profile_picture = request.FILES['profile_picture']
            
            # Save both profile and user
            profile.save()
            request.user.save()
            
            # ========== AVAILABILITY SCHEDULE ==========
            # Clear existing availability
            profile.availability_schedule.all().delete()
            
            # Save new availability
            days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
            day_map = {'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3, 
                      'friday': 4, 'saturday': 5, 'sunday': 6}
            
            for day in days:
                available = request.POST.get(f"{day}_available") == "on"
                if available:
                    start_time = request.POST.get(f"{day}_start")
                    end_time = request.POST.get(f"{day}_end")
                    
                    if start_time and end_time:
                        CaretakerAvailability.objects.create(
                            caretaker=profile,
                            day_of_week=day_map[day],
                            start_time=start_time,
                            end_time=end_time,
                            is_available=True
                        )
            
            messages.success(request, "Profile updated successfully!")
            return redirect('caretaker_profile')
            
        except Exception as e:
            messages.error(request, f"Error updating profile: {str(e)}")
            # Print error for debugging
            print(f"ERROR in profile update: {str(e)}")
            import traceback
            traceback.print_exc()
    
    # GET request - display the form
    # Get existing availability for form
    availability_dict = {}
    for avail in profile.availability_schedule.all():
        days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
        day_name = days[avail.day_of_week]
        availability_dict[day_name] = {
            'available': True,
            'start': avail.start_time.strftime('%H:%M') if avail.start_time else '',
            'end': avail.end_time.strftime('%H:%M') if avail.end_time else ''
        }
    
    # Create context with individual variables for each day
    context = {
        'profile': profile,
    }
    
    # Add individual day variables for the template
    days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
    for day in days:
        if day in availability_dict:
            context[f'{day}_available'] = True
            context[f'{day}_start'] = availability_dict[day]['start']
            context[f'{day}_end'] = availability_dict[day]['end']
        else:
            context[f'{day}_available'] = False
            context[f'{day}_start'] = ''
            context[f'{day}_end'] = ''
    
    return render(request, 'users/update_caretaker_profile.html', context)



# -------------------------------------------------------------------------
# Verification Pending Page (Caretaker)
# -------------------------------------------------------------------------

@login_required
def verification_pending(request):
    if request.user.role != "caretaker":
        return redirect("index")

    if request.user.is_verified:
        return redirect("caretaker_dashboard")

    return render(request, "users/verification_pending.html")


# -------------------------------------------------------------------------
# Search Caretakers (Family)
# -------------------------------------------------------------------------

@login_required
def search_caretakers(request):
    # Only families can search
    if request.user.role != "family":
        messages.error(request, "Access denied. Only families can search for caretakers.")
        return redirect("index")

    # Get all verified caretakers
    caretakers = CaretakerProfile.objects.filter(
        user__role="caretaker",
        user__is_verified=True
    ).select_related('user')

    # Apply filters
    query = request.GET.get("q")
    if query:
        caretakers = caretakers.filter(
            Q(user__first_name__icontains=query) |
            Q(user__last_name__icontains=query) |
            Q(qualification__icontains=query) |
            Q(city__icontains=query)
        )

    min_exp = request.GET.get("experience")
    if min_exp and min_exp.isdigit():
        caretakers = caretakers.filter(experience_years__gte=int(min_exp))

    availability = request.GET.get("availability")
    if availability:
        caretakers = caretakers.filter(availability_status=availability)

    return render(request, "users/search_caretakers.html", {
        "caretakers": caretakers,
    })


# -------------------------------------------------------------------------
# Caretaker Detail View
# -------------------------------------------------------------------------

@login_required
def caretaker_detail(request, id):
    # Only families can view caretaker details
    if request.user.role != "family":
        messages.error(request, "Access denied.")
        return redirect("index")

    caretaker = get_object_or_404(
        CaretakerProfile.objects.select_related('user'), 
        id=id,
        user__is_verified=True
    )

    return render(request, "users/caretaker_detail.html", {
        "caretaker": caretaker
    })


# -------------------------------------------------------------------------
# Family Profile Views
# -------------------------------------------------------------------------

@login_required
def family_profile(request):
    """View and display family profile"""
    if request.user.role != 'family':
        messages.error(request, "Access denied. This page is for family members only.")
        return redirect('index')
    
    try:
        profile = request.user.family_profile
    except FamilyProfile.DoesNotExist:
        # Create profile if it doesn't exist
        profile = FamilyProfile.objects.create(
            user=request.user,
            phone=request.user.phone or "",
            address="",
            patient_name="",
            patient_age=None,
            primary_medical_condition="",
            care_required=""
        )
        messages.info(request, "Please complete your profile information.")
    
    context = {
        'profile': profile,
        'user': request.user
    }
    return render(request, 'users/family_profile.html', context)


@login_required
def update_family_profile(request):
    """Update family profile with detailed information"""
    if request.user.role != 'family':
        messages.error(request, "Access denied.")
        return redirect('index')
    
    # Get or create profile
    try:
        profile = request.user.family_profile
    except FamilyProfile.DoesNotExist:
        profile = FamilyProfile.objects.create(
            user=request.user,
            phone=request.user.phone or ""
        )
    
    if request.method == "POST":
        try:
            # ========== CONTACT INFORMATION ==========
            profile.phone = request.POST.get("phone", "")
            profile.alternate_phone = request.POST.get("alternate_phone", "")
            profile.emergency_contact = request.POST.get("emergency_contact", "")
            
            # ========== ADDRESS DETAILS ==========
            profile.address = request.POST.get("address", "")
            profile.city = request.POST.get("city", "")
            profile.state = request.POST.get("state", "")
            profile.country = request.POST.get("country", "India")
            profile.pincode = request.POST.get("pincode", "")
            profile.landmark = request.POST.get("landmark", "")
            profile.residence_type = request.POST.get("residence_type", "apartment")
            
            # ========== FAMILY INFORMATION ==========
            profile.family_type = request.POST.get("family_type", "nuclear")
            
            family_size = request.POST.get("family_size")
            if family_size:
                profile.family_size = int(family_size)
            
            # ========== PATIENT INFORMATION ==========
            profile.patient_name = request.POST.get("patient_name", "")
            
            patient_age = request.POST.get("patient_age")
            if patient_age:
                profile.patient_age = int(patient_age)
            else:
                profile.patient_age = None
                
            profile.patient_gender = request.POST.get("patient_gender", "")
            profile.patient_blood_group = request.POST.get("patient_blood_group", "")
            
            # ========== MEDICAL INFORMATION ==========
            profile.primary_medical_condition = request.POST.get("primary_medical_condition", "")
            profile.secondary_conditions = request.POST.get("secondary_conditions", "")
            profile.allergies = request.POST.get("allergies", "")
            profile.medications = request.POST.get("medications", "")
            profile.dietary_restrictions = request.POST.get("dietary_restrictions", "")
            
            # ========== CARE REQUIREMENTS ==========
            profile.care_required = request.POST.get("care_required", "")
            profile.care_frequency = request.POST.get("care_frequency", "daily")
            
            # ========== HOME ENVIRONMENT ==========
            profile.pets_at_home = request.POST.get("pets_at_home") == "on"
            profile.pet_details = request.POST.get("pet_details", "")
            profile.smokers_in_home = request.POST.get("smokers_in_home") == "on"
            profile.accessibility_requirements = request.POST.get("accessibility_requirements", "")
            
            # ========== PREVIOUS CARETAKER ==========
            profile.previous_caretaker = request.POST.get("previous_caretaker") == "on"
            profile.previous_caretaker_feedback = request.POST.get("previous_caretaker_feedback", "")
            
            # ========== PREFERENCES ==========
            profile.preferred_caretaker_gender = request.POST.get("preferred_caretaker_gender", "any")
            profile.preferred_language = request.POST.get("preferred_language", "")
            
            monthly_budget = request.POST.get("monthly_budget")
            if monthly_budget:
                profile.monthly_budget = float(monthly_budget)
            else:
                profile.monthly_budget = None
            
            # ========== DOCUMENTS (File Uploads) ==========
            if 'identity_proof' in request.FILES:
                profile.identity_proof = request.FILES['identity_proof']
            if 'address_proof' in request.FILES:
                profile.address_proof = request.FILES['address_proof']
            if 'medical_reports' in request.FILES:
                profile.medical_reports = request.FILES['medical_reports']
            
            # Save the profile
            profile.save()
            
            # Update user phone if changed
            if request.user.phone != profile.phone:
                request.user.phone = profile.phone
                request.user.save()
            
            messages.success(request, "Profile updated successfully!")
            return redirect('family_profile')
            
        except Exception as e:
            messages.error(request, f"Error updating profile: {str(e)}")
            # Print error for debugging
            print(f"ERROR in profile update: {str(e)}")
            import traceback
            traceback.print_exc()
    
    context = {
        'profile': profile
    }
    return render(request, 'users/update_family_profile.html', context)


# -------------------------------------------------------------------------
# Dashboard Views
# -------------------------------------------------------------------------

@login_required
def caretaker_dashboard(request):
    """Caretaker dashboard view"""
    if request.user.role != 'caretaker':
        messages.error(request, "Access denied.")
        return redirect('index')
    
    # Clear any messages from previous pages (like login)
    storage = messages.get_messages(request)
    storage.used = True
    
    # Check verification status
    if not request.user.is_verified or request.user.verification_status != 'verified':
        return redirect('verification_pending')
    
    try:
        profile = request.user.caretaker_profile
    except CaretakerProfile.DoesNotExist:
        profile = None
    
    # Get statistics
    total_applications = 0  # This would come from applications app
    assigned_jobs = 0       # This would come from assignments app
    pending_applications = 0 # This would come from applications app
    
    context = {
        'profile': profile,
        'total_applications': total_applications,
        'assigned_jobs': assigned_jobs,
        'pending_applications': pending_applications,
    }
    return render(request, 'users/caretaker_dashboard.html', context)


@login_required
def family_dashboard(request):
    """Family dashboard view"""
    if request.user.role != 'family':
        messages.error(request, "Access denied.")
        return redirect('index')
    
    # Clear any messages from previous pages (like login)
    storage = messages.get_messages(request)
    storage.used = True
    
    try:
        profile = request.user.family_profile
    except FamilyProfile.DoesNotExist:
        profile = None
    
    context = {
        'profile': profile,
    }
    return render(request, 'users/family_dashboard.html', context)