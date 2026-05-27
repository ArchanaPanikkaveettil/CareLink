from datetime import datetime, timedelta, date
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q
from django.core.paginator import Paginator
from django.views.decorators.http import require_POST
from apps.Applications.models import CareApplication
from .models import CareRequest, CaretakerAvailability, CareBooking
from apps.Users.models import ElderProfile, User, CaretakerProfile
from django.urls import reverse
import calendar

from django.template.defaulttags import register


@register.filter
def get_item(dictionary, key):
    """Template filter to get dictionary item by key"""
    return dictionary.get(key)


# ============================================================================
# AVAILABILITY VIEWS
# ============================================================================

@login_required
def view_caretaker_availability(request, caretaker_id):
    """View a caretaker's availability calendar (for family members)"""
    caretaker_user = get_object_or_404(User, id=caretaker_id, role="caretaker")
    
    try:
        caretaker_profile = CaretakerProfile.objects.get(user=caretaker_user)
    except CaretakerProfile.DoesNotExist:
        caretaker_profile = None
    
    today = timezone.now().date()
    year = int(request.GET.get('year', today.year))
    month = int(request.GET.get('month', today.month))
    
    cal = calendar.monthcalendar(year, month)
    month_name = calendar.month_name[month]
    
    month_start = date(year, month, 1)
    if month == 12:
        month_end = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        month_end = date(year, month + 1, 1) - timedelta(days=1)
        
    slots = CaretakerAvailability.objects.filter(
        caretaker=caretaker_user,
        date__gte=month_start,
        date__lte=month_end,
    ).order_by('date', 'start_time')
    
    availability_by_date = {}
    for slot in slots:
        date_key = slot.date.strftime('%Y-%m-%d')
        if date_key not in availability_by_date:
            availability_by_date[date_key] = []
        availability_by_date[date_key].append(slot)
    
    if month == 1:
        prev_month = 12
        prev_year = year - 1
    else:
        prev_month = month - 1
        prev_year = year
    
    if month == 12:
        next_month = 1
        next_year = year + 1
    else:
        next_month = month + 1
        next_year = year
    
    context = {
        'caretaker': caretaker_user,
        'caretaker_profile': caretaker_profile,
        'calendar': cal,
        'year': year,
        'month': month,
        'month_name': month_name,
        'availability_by_date': availability_by_date,
        'prev_year': prev_year,
        'prev_month': prev_month,
        'next_year': next_year,
        'next_month': next_month,
    }
    
    return render(request, 'requests/caretaker_availability.html', context)


@login_required
def caretaker_availability_list(request):
    """List all availability slots for caretaker"""
    if request.user.role != "caretaker":
        messages.error(request, "Access denied.")
        return redirect("users:index")
    
    # Generate upcoming dates for display (next 30 days)
    today = date.today()
    slots = CaretakerAvailability.objects.filter(
        caretaker=request.user,
        date__gte=today
    ).order_by('date', 'start_time')
    
    available_slots = slots.filter(status='available')
    booked_slots = slots.filter(status='booked')
    
    total_slots = slots.count()
    available_count = available_slots.count()
    booked_count = booked_slots.count()
    recurring_slots_count = available_slots.filter(is_recurring=True).count()
    
    context = {
        'available_slots': available_slots,
        'booked_slots': booked_slots,
        'total_slots': total_slots,
        'available_count': available_count,
        'booked_count': booked_count,
        'recurring_slots_count': recurring_slots_count,
    }
    return render(request, 'requests/availability_list.html', context)


# ============================================================================
# FAMILY VIEWS - Find & Book Caretakers
# ============================================================================

@login_required
def find_caretakers(request):
    """Find caretakers (for family members)"""
    caretakers = CaretakerProfile.objects.all()

    q = request.GET.get("q")
    experience = request.GET.get("experience")
    availability = request.GET.get("availability")

    if q:
        caretakers = caretakers.filter(
            Q(user__first_name__icontains=q)
            | Q(user__last_name__icontains=q)
            | Q(qualification__icontains=q)
            | Q(city__icontains=q)
            | Q(state__icontains=q)
            | Q(address__icontains=q)
            | Q(skills__icontains=q)
            | Q(pincode__icontains=q)
        )

    if experience:
        caretakers = caretakers.filter(experience_years__gte=experience)

    if availability:
        caretakers = caretakers.filter(availability_status=availability)

    context = {"caretakers": caretakers}
    return render(request, "users/search_caretakers.html", context)


@login_required
def caretaker_detail(request, caretaker_id):
    """View detailed profile of a caretaker"""
    caretaker = get_object_or_404(User, id=caretaker_id, role='caretaker')
    
    try:
        profile = CaretakerProfile.objects.get(user=caretaker)
    except CaretakerProfile.DoesNotExist:
        profile = None
    
    context = {
        'caretaker': caretaker,
        'profile': profile,
    }
    return render(request, 'users/caretaker_detail.html', context)


# ============================================================================
# CARETAKER VIEWS - Browse & Apply to Requests
# ============================================================================

@login_required
def browse_requests(request):
    """Browse all open care requests (for caretakers)"""
    if request.user.role != "caretaker":
        messages.error(request, "Access denied. This page is for caretakers only.")
        return redirect("index")

    requests_list = CareRequest.objects.filter(status="open").order_by("-created_at")

    applied_request_ids = CareApplication.objects.filter(
        caretaker=request.user
    ).values_list("request_id", flat=True)

    search = request.GET.get("search")
    if search:
        requests_list = requests_list.filter(
            Q(patient_name__icontains=search)
            | Q(city__icontains=search)
            | Q(medical_condition__icontains=search)
        )

    care_type = request.GET.get("care_type")
    if care_type:
        requests_list = requests_list.filter(care_type=care_type)

    paginator = Paginator(requests_list, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "requests": page_obj,
        "applied_request_ids": applied_request_ids,
        "search": search,
        "care_type": care_type,
    }
    return render(request, "requests/browse_requests.html", context)


@login_required
def apply_for_request(request, request_id):
    """Apply for a care request (for caretakers)"""
    if request.user.role != "caretaker":
        messages.error(request, "❌ Access denied.")
        return redirect("index")

    if not request.user.is_verified:
        messages.warning(request, "⚠️ Please complete your verification before applying.")
        return redirect("verification_pending")

    care_request = get_object_or_404(CareRequest, id=request_id, status="open")

    if not care_request.can_apply():
        messages.error(request, "❌ This request is no longer accepting applications.")
        return redirect("requests:request_detail", request_id=care_request.id)

    # Check for existing application
    existing_app = CareApplication.objects.filter(
        request=care_request, caretaker=request.user
    ).first()

    if existing_app and existing_app.status != "withdrawn":
        messages.warning(request, "⚠️ You have already applied for this request.")
        return redirect("requests:request_detail", request_id=care_request.id)

    if request.method == "POST":
        message = request.POST.get("message", "").strip()
        proposed_rate = request.POST.get("proposed_rate")
        job_type = request.POST.get("job_type", care_request.care_type)

        work_start_time = request.POST.get("work_start_time")
        work_end_time = request.POST.get("work_end_time")
        work_days = request.POST.getlist("work_days")

        if not message or not proposed_rate:
            messages.error(request, "❌ All fields are required.")
            return render(
                request,
                "requests/apply_for_request.html",
                {"care_request": care_request, "job_type": job_type},
            )

        if job_type in ["part_time", "night_care", "home_visit"]:
            if not work_start_time or not work_end_time or not work_days:
                messages.error(
                    request,
                    "❌ Please specify working hours and days for part-time application.",
                )
                return render(
                    request,
                    "requests/apply_for_request.html",
                    {"care_request": care_request, "job_type": job_type},
                )

            try:
                work_days = [int(day) for day in work_days]
            except (ValueError, TypeError):
                messages.error(request, "❌ Invalid work days selected.")
                return render(
                    request, "requests/apply_for_request.html", {"care_request": care_request}
                )

        try:
            if existing_app:
                # Reactivate withdrawn application
                existing_app.message = message
                existing_app.proposed_rate = proposed_rate
                existing_app.status = "pending"
                existing_app.job_type = job_type
                existing_app.work_start_time = (
                    work_start_time if job_type != "full_time" else None
                )
                existing_app.work_end_time = (
                    work_end_time if job_type != "full_time" else None
                )
                existing_app.work_days = work_days if job_type != "full_time" else None
                existing_app.applied_at = timezone.now()
                existing_app.save()
            else:
                # Create new application
                CareApplication.objects.create(
                    request=care_request,
                    caretaker=request.user,
                    message=message,
                    proposed_rate=proposed_rate,
                    status="pending",
                    job_type=job_type,
                    work_start_time=work_start_time if job_type != "full_time" else None,
                    work_end_time=work_end_time if job_type != "full_time" else None,
                    work_days=work_days if job_type != "full_time" else None,
                )

            messages.success(request, "✅ Application submitted successfully!")
            return redirect("applications:my_applications")

        except Exception as e:
            messages.error(request, f"❌ Error submitting application: {str(e)}")
            return render(
                request, "requests/apply_for_request.html", {"care_request": care_request}
            )

    context = {
        "care_request": care_request,
        "job_type": care_request.care_type,
        "DAYS_OF_WEEK": CareApplication.DAYS_OF_WEEK,
    }
    return render(request, "requests/apply_for_request.html", context)


# ============================================================================
# FAMILY VIEWS - Request Management
# ============================================================================

@login_required
def post_request(request):
    """Post a new care request (for families)"""
    if request.user.role != "family":
        messages.error(request, "Only family members can post care requests.")
        return redirect("index")

    elders = ElderProfile.objects.filter(family=request.user).order_by('-is_primary', 'name')
    
    gender_choices = [("male", "Male"), ("female", "Female"), ("other", "Other")]
    mobility_choices = [("independent", "Independent"), ("walker", "Walker/Cane"), ("wheelchair", "Wheelchair"), ("bedridden", "Bedridden")]
    cognitive_choices = [("normal", "Normal"), ("mild_impairment", "Mild Cognitive Impairment"), ("dementia", "Dementia"), ("alzheimers", "Alzheimer's")]
    care_type_choices = [("full_time", "Full Time"), ("part_time", "Part Time"), ("night_care", "Night Care"), ("home_visit", "Home Visit"), ("emergency", "Emergency Care"), ("respite", "Respite Care"), ("palliative", "Palliative Care"), ("post_surgery", "Post-Surgery Care")]
    urgency_choices = [("low", "Low - Can wait"), ("medium", "Medium - Within a week"), ("high", "High - Within 2-3 days"), ("urgent", "Urgent - Immediately")]
    payment_choices = [("hourly", "Per Hour"), ("daily", "Per Day"), ("weekly", "Per Week"), ("monthly", "Per Month")]
    interview_choices = [("in_person", "In Person"), ("video", "Video Call"), ("phone", "Phone Call")]

    if request.method == "POST":
        try:
            elder_id = request.POST.get("elder_id")
            use_existing_elder = request.POST.get("use_existing_elder") == "on"
            
            patient_name = None
            patient_age = None
            patient_gender = None
            medical_condition = None
            mobility_status = None
            cognitive_status = None
            
            if use_existing_elder and elder_id:
                try:
                    elder = ElderProfile.objects.get(id=elder_id, family=request.user)
                    patient_name = elder.name
                    patient_age = elder.age
                    patient_gender = elder.gender
                    medical_condition = elder.medical_conditions
                    mobility_status = elder.mobility_status
                    cognitive_status = elder.cognitive_status
                except ElderProfile.DoesNotExist:
                    messages.warning(request, "Selected elder not found. Please use manual entry.")
                    use_existing_elder = False
            
            if not use_existing_elder or not patient_name:
                patient_name = request.POST.get("patient_name")
                patient_age = request.POST.get("patient_age")
                patient_gender = request.POST.get("patient_gender")
                medical_condition = request.POST.get("medical_condition")
                mobility_status = request.POST.get("mobility_status", "independent")
                cognitive_status = request.POST.get("cognitive_status", "normal")
            
            if not patient_name:
                messages.error(request, "Patient name is required.")
                return render(request, "requests/post_care_request.html", {
                    "elders": elders, "gender_choices": gender_choices, "mobility_choices": mobility_choices,
                    "cognitive_choices": cognitive_choices, "care_type_choices": care_type_choices,
                    "urgency_choices": urgency_choices, "payment_choices": payment_choices,
                    "interview_choices": interview_choices, "form_data": request.POST,
                })
            
            patient_age = int(patient_age) if patient_age else 0
            duration_days = int(request.POST.get("duration_days", 0))
            salary_offered = float(request.POST.get("salary_offered", 0))
            days_per_week = int(request.POST.get("days_per_week", 7))

            start_date = request.POST.get("start_date")
            if isinstance(start_date, str):
                start_date = datetime.strptime(start_date, "%Y-%m-%d").date()

            if start_date < timezone.now().date():
                messages.error(request, "Start date cannot be in the past.")
                return render(request, "requests/post_care_request.html", {
                    "elders": elders, "gender_choices": gender_choices, "mobility_choices": mobility_choices,
                    "cognitive_choices": cognitive_choices, "care_type_choices": care_type_choices,
                    "urgency_choices": urgency_choices, "payment_choices": payment_choices,
                    "interview_choices": interview_choices, "form_data": request.POST,
                })

            care_request = CareRequest(
                family=request.user,
                patient_name=patient_name,
                patient_age=patient_age,
                patient_gender=patient_gender,
                medical_condition=medical_condition,
                mobility_status=mobility_status,
                cognitive_status=cognitive_status,
                care_type=request.POST.get("care_type"),
                urgency_level=request.POST.get("urgency_level", "medium"),
                required_skills=request.POST.get("required_skills", ""),
                preferred_qualifications=request.POST.get("preferred_qualifications", ""),
                salary_offered=salary_offered,
                payment_frequency=request.POST.get("payment_frequency", "monthly"),
                negotiable=request.POST.get("negotiable") == "on",
                shift_timing=request.POST.get("shift_timing", ""),
                start_date=start_date,
                duration_days=duration_days,
                hours_per_day=request.POST.get("hours_per_day") or None,
                days_per_week=days_per_week,
                gender_preference=request.POST.get("gender_preference", "any"),
                age_preference_min=request.POST.get("age_preference_min") or None,
                age_preference_max=request.POST.get("age_preference_max") or None,
                language_preference=request.POST.get("language_preference", ""),
                address=request.POST.get("address"),
                city=request.POST.get("city", ""),
                state=request.POST.get("state", ""),
                pincode=request.POST.get("pincode", ""),
                landmark=request.POST.get("landmark", ""),
                special_requirements=request.POST.get("special_requirements", ""),
                equipment_provided=request.POST.get("equipment_provided", ""),
                accommodation_provided=request.POST.get("accommodation_provided") == "on",
                accommodation_details=request.POST.get("accommodation_details", ""),
                interview_required=request.POST.get("interview_required") == "on",
                interview_type=request.POST.get("interview_type", "video"),
                status="draft",
            )

            if use_existing_elder and elder_id:
                care_request.elder_profile_id = elder_id

            care_request.save()
            
            messages.success(request, "Care request created successfully! You can now publish it.")
            return redirect("requests:request_detail", request_id=care_request.id)

        except ValueError as e:
            messages.error(request, f"Invalid data format: {str(e)}")
        except Exception as e:
            messages.error(request, f"Error creating request: {str(e)}")

    return render(request, "requests/post_care_request.html", {
        "elders": elders, "gender_choices": gender_choices, "mobility_choices": mobility_choices,
        "cognitive_choices": cognitive_choices, "care_type_choices": care_type_choices,
        "urgency_choices": urgency_choices, "payment_choices": payment_choices,
        "interview_choices": interview_choices,
    })


@login_required
def publish_request(request, request_id):
    """Publish a draft request (for families)"""
    if request.user.role != "family":
        messages.error(request, "Access denied.")
        return redirect("index")

    care_request = get_object_or_404(CareRequest, id=request_id, family=request.user)

    if care_request.status == "draft":
        care_request.status = "open"
        care_request.published_at = timezone.now()
        care_request.save()
        messages.success(request, "Request published successfully! It is now visible to caregivers.")
    else:
        messages.error(request, "Only draft requests can be published.")

    return redirect("requests:request_detail", request_id=care_request.id)


@login_required
def my_requests(request):
    """View my posted requests (for families)"""
    if request.user.role != "family":
        messages.error(request, "Access denied.")
        return redirect("index")

    requests_list = CareRequest.objects.filter(family=request.user)

    status = request.GET.get("status")
    if status and status != "all":
        requests_list = requests_list.filter(status=status)

    search = request.GET.get("search")
    if search:
        requests_list = requests_list.filter(
            Q(patient_name__icontains=search)
            | Q(medical_condition__icontains=search)
            | Q(city__icontains=search)
        )

    requests_list = requests_list.order_by("-created_at")

    for req in requests_list:
        # Count excluding withdrawn
        req.total_applications = CareApplication.objects.filter(request=req).exclude(status="withdrawn").count()
        
        req.shortlisted_applications = CareApplication.objects.filter(
            request=req, status__in=["shortlisted", "offer_sent", "offer_accepted"]
        ).count()
        
        req.pending_applications = CareApplication.objects.filter(
            request=req, status="pending"
        ).count()
        
        req.offers_sent_count = CareApplication.objects.filter(
            request=req, status__in=["offer_sent", "offer_accepted"]
        ).count()
        
        req.has_active_shortlist = req.shortlisted_applications > 0

    open_count = requests_list.filter(status="open").count()
    draft_count = requests_list.filter(status="draft").count()
    assigned_count = requests_list.filter(status="assigned").count()
    closed_count = requests_list.filter(status="closed").count()

    paginator = Paginator(requests_list, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "requests": page_obj,
        "status_filter": status,
        "search": search,
        "open_count": open_count,
        "draft_count": draft_count,
        "assigned_count": assigned_count,
        "closed_count": closed_count,
    }
    return render(request, "requests/my_requests.html", context)


@login_required
def request_detail(request, request_id):
    """View details of a specific request"""
    care_request = get_object_or_404(CareRequest, id=request_id)

    if request.user.role == "family" and care_request.family != request.user:
        messages.error(request, "You do not have permission to view this request.")
        return redirect("index")

    has_applied = False
    application_status = None
    if request.user.role == "caretaker":
        application = CareApplication.objects.filter(
            caretaker=request.user, request=care_request
        ).first()
        if application:
            application_status = application.status
            if application.status != "withdrawn":
                has_applied = True

    from django.db.models import Count
    from apps.assignments.models import CareAssignment

    # Calculate application stats, excluding withdrawn ones
    application_stats = (
        CareApplication.objects.filter(request=care_request)
        .exclude(status="withdrawn")
        .aggregate(
            total=Count("id"),
            pending=Count("id", filter=Q(status="pending")),
            shortlisted=Count("id", filter=Q(status="shortlisted")),
            accepted=Count("id", filter=Q(status="accepted")),
            rejected=Count("id", filter=Q(status="rejected")),
        )
    )

    assignment = CareAssignment.objects.filter(care_request=care_request).first()
    # If assigned_caretaker field is null but an assignment exists, link them
    if not care_request.assigned_caretaker and assignment:
        # We don't save it to DB here to avoid side effects during GET, 
        # but we pass it in context or temporarily attach it
        care_request.assigned_caretaker = assignment.caretaker

    context = {
        "care_request": care_request,
        "assignment": assignment,
        "user": request.user,
        "has_applied": has_applied,
        "application_status": application_status,
        "application_stats": application_stats,
        "base_template": "users/nurse_base.html" if request.user.role == "caretaker" else "users/family_base.html",
    }
    return render(request, "requests/request_detail.html", context)


@login_required
def edit_request(request, request_id):
    """Edit a care request (for families)"""
    if request.user.role != "family":
        messages.error(request, "❌ Access denied.")
        return redirect("index")

    care_request = get_object_or_404(CareRequest, id=request_id, family=request.user)

    if not care_request.can_edit():
        messages.error(
            request,
            f"❌ This request cannot be edited. Only drafts can be edited. Current status: {care_request.get_status_display()}",
        )
        return redirect("requests:request_detail", request_id=care_request.id)

    if request.method == "POST":
        try:
            action = request.POST.get("action", "")

            care_request.patient_name = request.POST.get("patient_name", care_request.patient_name)

            patient_age = request.POST.get("patient_age")
            if patient_age:
                care_request.patient_age = int(patient_age)

            patient_gender = request.POST.get("patient_gender")
            if patient_gender:
                care_request.patient_gender = patient_gender

            care_request.medical_condition = request.POST.get("medical_conditions", care_request.medical_condition)
            care_request.mobility_status = request.POST.get("mobility_status", care_request.mobility_status)
            care_request.cognitive_status = request.POST.get("cognitive_status", care_request.cognitive_status)
            care_request.care_type = request.POST.get("care_type", care_request.care_type)
            care_request.urgency_level = request.POST.get("urgency_level", care_request.urgency_level)

            salary = request.POST.get("salary_offered")
            if salary:
                care_request.salary_offered = float(salary)

            care_request.payment_frequency = request.POST.get("payment_frequency", care_request.payment_frequency)
            care_request.negotiable = request.POST.get("negotiable") == "on"

            start_date = request.POST.get("start_date")
            if start_date:
                care_request.start_date = datetime.strptime(start_date, "%Y-%m-%d").date()

            care_request.shift_timing = request.POST.get("shift_timing", care_request.shift_timing)

            duration = request.POST.get("duration_days")
            if duration:
                care_request.duration_days = int(duration)

            hours_per_day = request.POST.get("hours_per_day")
            if hours_per_day:
                care_request.hours_per_day = float(hours_per_day)

            days_per_week = request.POST.get("days_per_week")
            if days_per_week:
                care_request.days_per_week = int(days_per_week)

            care_request.address = request.POST.get("address", care_request.address)
            care_request.city = request.POST.get("city", care_request.city)
            care_request.state = request.POST.get("state", care_request.state)
            care_request.pincode = request.POST.get("pincode", care_request.pincode)
            care_request.landmark = request.POST.get("landmark", care_request.landmark)
            care_request.gender_preference = request.POST.get("gender_preference", care_request.gender_preference)

            age_min = request.POST.get("age_preference_min")
            if age_min:
                care_request.age_preference_min = int(age_min)

            age_max = request.POST.get("age_preference_max")
            if age_max:
                care_request.age_preference_max = int(age_max)

            care_request.language_preference = request.POST.get("language_preference", care_request.language_preference)
            care_request.required_skills = request.POST.get("required_skills", care_request.required_skills)
            care_request.preferred_qualifications = request.POST.get("preferred_qualifications", care_request.preferred_qualifications)
            care_request.special_requirements = request.POST.get("special_requirements", care_request.special_requirements)
            care_request.equipment_provided = request.POST.get("equipment_provided", care_request.equipment_provided)
            care_request.accommodation_provided = request.POST.get("accommodation_provided") == "on"
            care_request.accommodation_details = request.POST.get("accommodation_details", care_request.accommodation_details)
            care_request.interview_required = request.POST.get("interview_required") == "on"
            care_request.interview_type = request.POST.get("interview_type", care_request.interview_type)
            care_request.emergency_contact_name = request.POST.get("emergency_contact_name", care_request.emergency_contact_name)
            care_request.emergency_contact_phone = request.POST.get("emergency_contact_phone", care_request.emergency_contact_phone)
            care_request.care_details = request.POST.get("care_details", care_request.care_details)

            if action == "publish" and care_request.status == "draft":
                care_request.publish()
                messages.success(request, "✅ Request published successfully!")
                return redirect("requests:request_detail", request_id=care_request.id)
            elif action == "save_draft":
                care_request.status = "draft"
                care_request.save()
                messages.success(request, "✅ Draft saved successfully!")
                return redirect("requests:my_requests")
            else:
                care_request.save()
                messages.success(request, "✅ Request updated successfully!")
                return redirect("requests:request_detail", request_id=care_request.id)

        except ValueError as e:
            messages.error(request, f"❌ Invalid data format: {str(e)}")
        except Exception as e:
            messages.error(request, f"❌ Error updating request: {str(e)}")

    applications_count = CareApplication.objects.filter(request=care_request).count()
    pending_count = CareApplication.objects.filter(request=care_request, status="pending").count()
    shortlisted_count = CareApplication.objects.filter(request=care_request, status="shortlisted").count()
    offers_sent_count = CareApplication.objects.filter(request=care_request, status__in=["offer_sent", "offer_accepted", "offer_declined"]).count()

    context = {
        "care_request": care_request,
        "applications_count": applications_count,
        "pending_count": pending_count,
        "shortlisted_count": shortlisted_count,
        "offers_sent_count": offers_sent_count,
        "has_applications": applications_count > 0,
        "errors": {},
        "STATUS_CHOICES": CareRequest.STATUS_CHOICES,
        "CARE_TYPES": CareRequest.CARE_TYPES,
        "GENDER_PREFERENCES": CareRequest.GENDER_PREFERENCES,
        "PAYMENT_FREQUENCY": CareRequest.PAYMENT_FREQUENCY,
        "URGENCY_LEVELS": CareRequest.URGENCY_LEVELS,
    }
    return render(request, "requests/edit_request.html", context)


@login_required
def save_draft(request, request_id):
    """Save draft without publishing (for families)"""
    if request.user.role != "family":
        messages.error(request, "❌ Access denied.")
        return redirect("index")

    care_request = get_object_or_404(CareRequest, id=request_id, family=request.user)

    if not care_request.can_edit():
        messages.error(request, "❌ Only draft requests can be saved as draft.")
        return redirect("requests:request_detail", request_id=care_request.id)

    if request.method == "POST":
        try:
            care_request.patient_name = request.POST.get("patient_name", care_request.patient_name)
            
            patient_age = request.POST.get("patient_age")
            if patient_age:
                care_request.patient_age = int(patient_age)
            
            patient_gender = request.POST.get("patient_gender")
            if patient_gender:
                care_request.patient_gender = patient_gender
                
            care_request.medical_condition = request.POST.get("medical_condition", care_request.medical_condition)
            care_request.mobility_status = request.POST.get("mobility_status", care_request.mobility_status)
            care_request.cognitive_status = request.POST.get("cognitive_status", care_request.cognitive_status)
            care_request.care_type = request.POST.get("care_type", care_request.care_type)
            care_request.urgency_level = request.POST.get("urgency_level", care_request.urgency_level)
            
            salary = request.POST.get("salary_offered")
            if salary:
                care_request.salary_offered = float(salary)
                
            care_request.payment_frequency = request.POST.get("payment_frequency", care_request.payment_frequency)
            care_request.negotiable = request.POST.get("negotiable") == "on"
            
            start_date = request.POST.get("start_date")
            if start_date:
                care_request.start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
                
            care_request.shift_timing = request.POST.get("shift_timing", care_request.shift_timing)
            
            duration = request.POST.get("duration_days")
            if duration:
                care_request.duration_days = int(duration)
                
            hours_per_day = request.POST.get("hours_per_day")
            if hours_per_day:
                care_request.hours_per_day = float(hours_per_day)
                
            days_per_week = request.POST.get("days_per_week")
            if days_per_week:
                care_request.days_per_week = int(days_per_week)
                
            care_request.address = request.POST.get("address", care_request.address)
            care_request.city = request.POST.get("city", care_request.city)
            care_request.state = request.POST.get("state", care_request.state)
            care_request.pincode = request.POST.get("pincode", care_request.pincode)
            care_request.landmark = request.POST.get("landmark", care_request.landmark)
            care_request.gender_preference = request.POST.get("gender_preference", care_request.gender_preference)
            
            age_min = request.POST.get("age_preference_min")
            if age_min:
                care_request.age_preference_min = int(age_min)
                
            age_max = request.POST.get("age_preference_max")
            if age_max:
                care_request.age_preference_max = int(age_max)
                
            care_request.language_preference = request.POST.get("language_preference", care_request.language_preference)
            care_request.required_skills = request.POST.get("required_skills", care_request.required_skills)
            care_request.preferred_qualifications = request.POST.get("preferred_qualifications", care_request.preferred_qualifications)
            care_request.special_requirements = request.POST.get("special_requirements", care_request.special_requirements)
            care_request.equipment_provided = request.POST.get("equipment_provided", care_request.equipment_provided)
            care_request.accommodation_provided = request.POST.get("accommodation_provided") == "on"
            care_request.accommodation_details = request.POST.get("accommodation_details", care_request.accommodation_details)
            care_request.interview_required = request.POST.get("interview_required") == "on"
            care_request.interview_type = request.POST.get("interview_type", care_request.interview_type)
            care_request.emergency_contact_name = request.POST.get("emergency_contact_name", care_request.emergency_contact_name)
            care_request.emergency_contact_phone = request.POST.get("emergency_contact_phone", care_request.emergency_contact_phone)
            care_request.care_details = request.POST.get("care_details", care_request.care_details)
            
            care_request.status = "draft"
            care_request.save()
            
            messages.success(request, "✅ Draft saved successfully! You can continue editing later.")
            
        except Exception as e:
            messages.error(request, f"❌ Error saving draft: {str(e)}")

        return redirect("requests:my_requests")

    return redirect("requests:request_detail", request_id=care_request.id)


@login_required
def close_request(request, request_id):
    """Close a care request"""
    if request.user.role != 'family':
        messages.error(request, 'Only family members can close requests.')
        return redirect('index')
    
    try:
        care_request = get_object_or_404(CareRequest, id=request_id, family=request.user)
        
        if care_request.status == 'open':
            care_request.status = 'closed'
            care_request.closed_at = timezone.now()
            care_request.save()
            
            from apps.Applications.models import CareApplication
            CareApplication.objects.filter(request=care_request, status='pending').update(
                status='rejected', 
                rejection_note='Request closed by family'
            )
            
            messages.success(request, f'Care request for {care_request.patient_name} has been closed successfully.')
        else:
            messages.warning(request, f'Only open requests can be closed. Current status: {care_request.get_status_display()}')
        
        return redirect('requests:my_requests')
        
    except CareRequest.DoesNotExist:
        messages.error(request, 'Care request not found or you do not have permission to close it.')
        return redirect('requests:my_requests')
    except AttributeError as e:
        messages.error(request, f'Error: {str(e)}')
        return redirect('requests:my_requests')


@login_required
def delete_request(request, request_id):
    """Delete a care request (for families)"""
    care_request = get_object_or_404(CareRequest, id=request_id, family=request.user)

    if request.method == "POST":
        if care_request.status not in ["draft", "closed", "open"]:
            messages.error(
                request, f"❌ Only draft, open, or closed requests can be deleted."
            )
            return redirect("requests:request_detail", request_id=care_request.id)

        patient_name = care_request.patient_name
        care_request.delete()
        messages.success(
            request,
            f"✅ Care request for {patient_name} has been deleted successfully.",
        )
        return redirect("requests:my_requests")

    return render(
        request, "requests/delete_request_confirm.html", {"request_obj": care_request}
    )


# ============================================================================
# BOOKING VIEWS
# ============================================================================

@login_required
def book_caretaker(request, caretaker_id, slot_id):
    """Directly book a caretaker based on an availability slot"""
    if request.user.role != "family":
        messages.error(request, "Only family members can book caretakers")
        return redirect("users:index")

    caretaker_user = get_object_or_404(User, id=caretaker_id, role="caretaker")
    slot = get_object_or_404(CaretakerAvailability, id=slot_id, caretaker=caretaker_user)

    if slot.status != "available":
        messages.error(request, "This time slot is no longer available.")
        return redirect("requests:caretaker_availability", caretaker_id=caretaker_user.id)

    user_requests = CareRequest.objects.filter(family=request.user, status="open")

    if request.method == "POST":
        selected_request_id = request.POST.get("care_request_id")
        family_notes = request.POST.get("family_notes", "")

        if not selected_request_id:
            messages.error(request, "Please select an open care request to link with this booking.")
            return redirect("requests:book_caretaker", caretaker_id=caretaker_user.id, slot_id=slot.id)

        care_request = get_object_or_404(CareRequest, id=selected_request_id, family=request.user)

        try:
            start_datetime = datetime.combine(slot.date, slot.start_time)
            end_datetime = datetime.combine(slot.date, slot.end_time)
            duration_hours = (end_datetime - start_datetime).seconds / 3600

            booking = CareBooking.objects.create(
                care_request=care_request,
                caretaker=caretaker_user,
                family=request.user,
                booking_date=slot.date,
                start_time=slot.start_time,
                end_time=slot.end_time,
                duration_hours=duration_hours,
                status="pending",
                family_notes=family_notes,
            )

            slot.status = "booked"
            slot.booked_request = care_request
            slot.save()

            from apps.Notifications.models import Notification

            Notification.objects.create(
                recipient=caretaker_user,
                sender=request.user,
                notification_type="booking",
                title="New Direct Booking Request",
                message=f"{request.user.get_full_name()} has requested a direct booking on {slot.date} at {slot.start_time}",
                icon="fa-calendar-plus",
                link=f"/requests/booking/{booking.id}/",
                is_read=False,
            )

            messages.success(request, f"Booking request successfully sent to {caretaker_user.get_full_name()}!")
            return redirect("requests:my_bookings")

        except Exception as e:
            messages.error(request, f"Error creating booking: {str(e)}")

    context = {
        "caretaker": caretaker_user,
        "slot": slot,
        "user_requests": user_requests,
    }
    return render(request, "requests/book_caretaker.html", context)


@login_required
def book_caretaker_multi(request, caretaker_id):
    """Multi-slot booking: family can pick a date range, per-day or random slots."""
    if request.user.role != "family":
        messages.error(request, "Only family members can book caretakers.")
        return redirect("users:index")

    caretaker_user = get_object_or_404(User, id=caretaker_id, role="caretaker")

    # Fetch all future available slots for this caretaker
    available_slots = CaretakerAvailability.objects.filter(
        caretaker=caretaker_user,
        status="available",
        date__gte=date.today(),
    ).order_by("date", "start_time")

    user_requests = CareRequest.objects.filter(family=request.user, status="open")

    if request.method == "POST":
        slot_ids = request.POST.getlist("slot_ids")
        selected_request_id = request.POST.get("care_request_id")
        family_notes = request.POST.get("family_notes", "")

        if not slot_ids:
            messages.error(request, "Please select at least one date slot.")
            return redirect("requests:book_caretaker_multi", caretaker_id=caretaker_user.id)

        if not selected_request_id:
            messages.error(request, "Please select an open care request to link with this booking.")
            return redirect("requests:book_caretaker_multi", caretaker_id=caretaker_user.id)

        care_request = get_object_or_404(CareRequest, id=selected_request_id, family=request.user)

        created_count = 0
        skipped_count = 0

        from apps.Notifications.models import Notification

        for slot_id in slot_ids:
            try:
                slot = CaretakerAvailability.objects.get(
                    id=slot_id,
                    caretaker=caretaker_user,
                    status="available"
                )
                start_dt = datetime.combine(slot.date, slot.start_time)
                end_dt = datetime.combine(slot.date, slot.end_time)
                duration_hours = (end_dt - start_dt).seconds / 3600

                CareBooking.objects.create(
                    care_request=care_request,
                    caretaker=caretaker_user,
                    family=request.user,
                    booking_date=slot.date,
                    start_time=slot.start_time,
                    end_time=slot.end_time,
                    duration_hours=duration_hours,
                    status="pending",
                    family_notes=family_notes,
                )
                # Don't lock the slot yet — only lock it when the caretaker accepts.
                # This allows the caretaker to see it's being requested without forcing the slot closed.
                slot.booked_request = care_request
                slot.save()
                created_count += 1

            except CaretakerAvailability.DoesNotExist:
                skipped_count += 1
            except Exception:
                skipped_count += 1

        if created_count > 0:
            Notification.objects.create(
                recipient=caretaker_user,
                sender=request.user,
                notification_type="booking",
                title="New Multi-Day Booking Request",
                message=f"{request.user.get_full_name()} has requested {created_count} booking slot(s) starting from the selected dates.",
                icon="fa-calendar-plus",
                link="/requests/my-bookings/",
                is_read=False,
            )
            if skipped_count > 0:
                messages.warning(request, f"✅ Booked {created_count} slot(s). {skipped_count} slot(s) were already taken and skipped.")
            else:
                messages.success(request, f"✅ Successfully sent {created_count} booking request(s) to {caretaker_user.get_full_name()}!")
        else:
            messages.error(request, "No slots could be booked. They may have already been taken.")

        return redirect("requests:my_bookings")

    context = {
        "caretaker": caretaker_user,
        "available_slots": available_slots,
        "user_requests": user_requests,
    }
    return render(request, "requests/book_caretaker_multi.html", context)


@login_required
def create_booking_request(request, caretaker_id):
    """Create a minimal CareRequest inline during the direct booking flow."""
    if request.user.role != "family":
        messages.error(request, "Only family members can create care requests.")
        return redirect("users:index")

    caretaker_user = get_object_or_404(User, id=caretaker_id, role="caretaker")

    if request.method == "POST":
        try:
            from django.utils.crypto import get_random_string
            req_id = "CR-" + get_random_string(6).upper()

            care_req = CareRequest.objects.create(
                request_id=req_id,
                family=request.user,
                patient_name=request.POST.get("patient_name", "").strip(),
                patient_age=int(request.POST.get("patient_age", 60)),
                patient_gender=request.POST.get("patient_gender", "other"),
                medical_condition=request.POST.get("medical_condition", "General care needed"),
                care_type=request.POST.get("care_type", "part_time"),
                urgency_level=request.POST.get("urgency_level", "medium"),
                required_skills=request.POST.get("required_skills", "General caregiving"),
                salary_offered=float(request.POST.get("salary_offered", 500)),
                payment_frequency=request.POST.get("payment_frequency", "hourly"),
                shift_timing=request.POST.get("shift_timing", "Flexible"),
                start_date=date.today(),
                duration_days=int(request.POST.get("duration_days", 7)),
                address=request.POST.get("address", ""),
                city=request.POST.get("city", ""),
                state=request.POST.get("state", "Kerala"),
                pincode=request.POST.get("pincode", "000000"),
                status="open",
                interview_required=False,
                interview_type="phone",
                mobility_status="independent",
                cognitive_status="normal",
            )
            messages.success(request, f"✅ Care request for {care_req.patient_name} created! Now select dates to book.")
        except Exception as e:
            messages.error(request, f"Error creating care request: {str(e)}")

    return redirect("requests:book_caretaker_multi", caretaker_id=caretaker_user.id)


@login_required
def my_bookings(request):
    """View all bookings for the current user"""
    if request.user.role == "family":
        bookings = CareBooking.objects.filter(family=request.user).order_by(
            "-booking_date", "-created_at"
        )
    elif request.user.role == "caretaker":
        bookings = CareBooking.objects.filter(caretaker=request.user).order_by(
            "-booking_date", "-created_at"
        )
    else:
        messages.error(request, "Access denied")
        return redirect("index")

    status_filter = request.GET.get("status")
    if status_filter and status_filter != "all":
        bookings = bookings.filter(status=status_filter)

    paginator = Paginator(bookings, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    counts = {
        "pending": bookings.filter(status="pending").count(),
        "confirmed": bookings.filter(status="confirmed").count(),
        "in_progress": bookings.filter(status="in_progress").count(),
        "completed": bookings.filter(status="completed").count(),
        "cancelled": bookings.filter(status="cancelled").count(),
    }

    context = {
        "bookings": page_obj,
        "counts": counts,
        "status_filter": status_filter,
        "base_template": "users/nurse_base.html" if request.user.role == 'caretaker' else "users/family_base.html"
    }
    return render(request, "requests/my_bookings.html", context)


@login_required
def booking_detail(request, booking_id):
    """View booking details"""
    booking = get_object_or_404(CareBooking, id=booking_id)

    if request.user != booking.family and request.user != booking.caretaker:
        messages.error(request, "Access denied")
        return redirect("index")

    context = {
        "booking": booking,
        "is_family": request.user == booking.family,
        "is_caretaker": request.user == booking.caretaker,
        "base_template": "users/nurse_base.html" if request.user.role == 'caretaker' else "users/family_base.html"
    }
    return render(request, "requests/booking_detail.html", context)


@login_required
@require_POST
def confirm_booking(request, booking_id):
    """Confirm a booking (caretaker action)"""
    booking = get_object_or_404(CareBooking, id=booking_id, caretaker=request.user)

    if booking.status != "pending":
        messages.error(request, "This booking cannot be confirmed")
        return redirect("requests:booking_detail", booking_id=booking.id)

    confirmation_message = request.POST.get("confirmation_message", "").strip()

    if booking.confirm_booking():
        from apps.Notifications.models import Notification
        
        booking.confirmation_message = confirmation_message
        booking.save(update_fields=['confirmation_message'])

        # NOW lock the availability slot — caretaker has accepted
        CaretakerAvailability.objects.filter(
            caretaker=booking.caretaker,
            date=booking.booking_date,
            start_time=booking.start_time,
        ).update(status="booked", booked_request=booking.care_request)

        msg_body = f"{request.user.get_full_name()} has accepted your booking for {booking.booking_date.strftime('%d %b %Y')}."
        if confirmation_message:
            msg_body += f"\n\nMessage: {confirmation_message}"

        Notification.objects.create(
            recipient=booking.family,
            sender=request.user,
            notification_type="booking",
            title="✅ Booking Confirmed!",
            message=msg_body,
            icon="fa-calendar-check",
            link=f"/requests/booking/{booking.id}/",
            is_read=False,
        )
        messages.success(request, "Booking confirmed successfully!")
    else:
        messages.error(request, "Failed to confirm booking")

    return redirect("requests:booking_detail", booking_id=booking.id)


@login_required
@require_POST
def cancel_booking(request, booking_id):
    """Cancel a booking"""
    booking = get_object_or_404(CareBooking, id=booking_id)

    if request.user != booking.family and request.user != booking.caretaker:
        messages.error(request, "Access denied")
        return redirect("users:index")

    if booking.status in ["completed", "cancelled"]:
        messages.error(request, "This booking cannot be cancelled")
        return redirect("requests:booking_detail", booking_id=booking.id)
        
    cancellation_reason = request.POST.get("cancellation_reason", "").strip()

    if booking.cancel_booking():
        from apps.Notifications.models import Notification
        
        booking.cancellation_reason = cancellation_reason
        booking.save(update_fields=['cancellation_reason'])

        recipient = (
            booking.family if request.user == booking.caretaker else booking.caretaker
        )
        
        msg_body = f"{request.user.get_full_name()} has cancelled the booking for {booking.booking_date.strftime('%d %b %Y')}."
        if cancellation_reason:
            msg_body += f"\n\nReason: {cancellation_reason}"
            
        Notification.objects.create(
            recipient=recipient,
            sender=request.user,
            notification_type="booking",
            title="❌ Booking Cancelled",
            message=msg_body,
            icon="fa-calendar-times",
            link=f"/requests/booking/{booking.id}/",
            is_read=False,
        )
        # Free the availability slot back
        CaretakerAvailability.objects.filter(
            caretaker=booking.caretaker,
            date=booking.booking_date,
            start_time=booking.start_time,
            status="booked"
        ).update(status="available", booked_request=None)
        messages.success(request, "Booking cancelled successfully!")
    else:
        messages.error(request, "Failed to cancel booking")

    return redirect("requests:booking_detail", booking_id=booking.id)


@login_required
@require_POST
def complete_booking(request, booking_id):
    """Complete a booking"""
    booking = get_object_or_404(CareBooking, id=booking_id)

    if request.user != booking.caretaker:
        messages.error(request, "Only the caretaker can complete a booking")
        return redirect("requests:booking_detail", booking_id=booking.id)

    if booking.status != "in_progress":
        messages.error(request, "This booking cannot be completed")
        return redirect("requests:booking_detail", booking_id=booking.id)

    completion_notes = request.POST.get("completion_notes", "").strip()

    if booking.complete_booking():
        from apps.Notifications.models import Notification
        
        booking.completion_notes = completion_notes
        booking.save(update_fields=['completion_notes'])

        msg_body = f"{request.user.get_full_name()} has completed the care session on {booking.booking_date.strftime('%d %b %Y')}."
        if completion_notes:
            msg_body += f"\n\nNotes: {completion_notes}"

        Notification.objects.create(
            recipient=booking.family,
            sender=request.user,
            notification_type="booking",
            title="🎉 Care Session Completed!",
            message=msg_body,
            icon="fa-check-circle",
            link=f"/requests/booking/{booking.id}/",
            is_read=False,
        )
        messages.success(request, "Care session completed!")
    else:
        messages.error(request, "Failed to complete booking")

    return redirect("requests:booking_detail", booking_id=booking.id)


@login_required
@require_POST
def start_booking(request, booking_id):
    """Start a booking (mark as in progress)"""
    booking = get_object_or_404(CareBooking, id=booking_id)

    if request.user != booking.caretaker:
        messages.error(request, "Only the caretaker can start a booking")
        return redirect("requests:booking_detail", booking_id=booking.id)

    if booking.status != "confirmed":
        messages.error(request, "This booking cannot be started")
        return redirect("requests:booking_detail", booking_id=booking.id)

    start_notes = request.POST.get("start_notes", "").strip()

    booking.status = "in_progress"
    booking.start_notes = start_notes
    booking.save()

    from apps.Notifications.models import Notification

    msg_body = f"{request.user.get_full_name()} has started the care session for {booking.booking_date.strftime('%d %b %Y')}."
    if start_notes:
        msg_body += f"\n\nNotes: {start_notes}"

    Notification.objects.create(
        recipient=booking.family,
        sender=request.user,
        notification_type="booking",
        title="🚀 Care Session Started!",
        message=msg_body,
        icon="fa-play-circle",
        link=f"/requests/booking/{booking.id}/",
        is_read=False,
    )

    messages.success(request, "Care session started!")
    return redirect("requests:booking_detail", booking_id=booking.id)


@login_required
@require_POST
def submit_booking_review(request, booking_id):
    """Submit a review for a booking (family action)"""
    booking = get_object_or_404(CareBooking, id=booking_id, family=request.user)

    if booking.status not in ["completed", "in_progress", "confirmed"]:
        messages.error(request, "You can only review confirmed, completed or in-progress sessions.")
        return redirect("requests:booking_detail", booking_id=booking.id)

    rating = request.POST.get("rating")
    comment = request.POST.get("comment", "").strip()

    if not rating:
        messages.error(request, "Please provide a rating.")
        return redirect("requests:booking_detail", booking_id=booking.id)

    from apps.Users.models import CaretakerReview

    # If the booking is not completed, complete it now
    if booking.status != "completed":
        booking.complete_booking()
        # Also free the slot if it was still locked
        from apps.Users.models import CaretakerAvailability
        CaretakerAvailability.objects.filter(
            caretaker=booking.caretaker,
            date=booking.booking_date,
            start_time=booking.start_time,
            status="booked"
        ).update(status="available", booked_request=None)
        
    # Create or update review
    CaretakerReview.objects.update_or_create(
        booking=booking,
        defaults={
            "caretaker": booking.caretaker.caretaker_profile,
            "family": booking.family.family_profile,
            "rating": int(rating),
            "comment": comment
        }
    )

    messages.success(request, "Thank you for your review! Session marked as completed.")
    return redirect("requests:booking_detail", booking_id=booking.id)


# ============================================================================
# CARETAKER AVAILABILITY MANAGEMENT
# ============================================================================

@login_required
def caretaker_set_availability(request):
    """Set availability for caretaker (specific dates) and checks full-time conflicts"""
    import json
    from django.db.models import Q
    from apps.assignments.models import CareAssignment
    from .models import CaretakerAvailability

    if request.user.role != "caretaker":
        messages.error(request, "Only caretakers can set availability")
        return redirect("users:index")

    if request.method == "POST":
        mode = request.POST.get("mode", "dateRange")

        try:
            dates_to_add = []
            if mode in ["dateRange", "multipleDates"]:
                selected_dates_json = request.POST.get("selected_dates", "[]")
                selected_dates = json.loads(selected_dates_json)
                
                if not selected_dates:
                    messages.error(request, "Please select at least one date.")
                    return redirect("requests:set_availability")
                
                for dt_str in selected_dates:
                    dates_to_add.append(datetime.strptime(dt_str, "%Y-%m-%d").date())

            elif mode == "weekly":
                selected_weekdays_json = request.POST.get("selected_weekdays", "[]")
                selected_weekdays = json.loads(selected_weekdays_json)
                if not selected_weekdays:
                    messages.error(request, "Please select at least one day of the week.")
                    return redirect("requests:set_availability")
                
                # Generate dates for the next 90 days matching the weekdays
                today_date = date.today()
                for i in range(90):
                    curr = today_date + timedelta(days=i)
                    if str(curr.weekday()) in selected_weekdays:
                        dates_to_add.append(curr)
                
                if not dates_to_add:
                    messages.error(request, "Could not map selected days to the calendar.")
                    return redirect("requests:set_availability")
            
            # Extract time slots
            time_slots = []
            i = 0
            while True:
                start_str = request.POST.get(f"start_time_{i}")
                end_str = request.POST.get(f"end_time_{i}")
                if start_str and end_str:
                    st = datetime.strptime(start_str, "%H:%M").time()
                    et = datetime.strptime(end_str, "%H:%M").time()
                    if et <= st:
                        messages.error(request, f"End time ({end_str}) must be after start time ({start_str}).")
                        return redirect("requests:set_availability")
                    time_slots.append((st, et))
                    i += 1
                else:
                    break
            
            if not time_slots:
                messages.error(request, "Please add at least one valid time slot.")
                return redirect("requests:set_availability")

            # Check for Live-In commitments
            # Caretakers cannot be available on dates if they are engaged in a 24-hour live-in assignment.
            # (If full_time or part_time, they can set availability for their off-hours).
            active_live_in_jobs = CareAssignment.objects.filter(
                caretaker=request.user,
                status="active",
                shift_type="live_in"
            )

            # Process additions
            created_count = 0
            skipped_conflicts = 0

            for d in set(dates_to_add):
                # Is caretaker locked into a full-time rule on this date?
                has_conflict = False
                for job in active_live_in_jobs:
                    # if job end_date is None, it means the job is ongoing indefinitely
                    if job.start_date <= d and (job.end_date is None or job.end_date >= d):
                        has_conflict = True
                        break

                if has_conflict:
                    skipped_conflicts += 1
                    continue

                for (st, et) in time_slots:
                    # Create or update availability entry
                    CaretakerAvailability.objects.update_or_create(
                        caretaker=request.user,
                        date=d,
                        start_time=st,
                        defaults={
                            "end_time": et,
                            "status": "available",
                            "is_recurring": (mode == "weekly")
                        }
                    )
                    created_count += 1
            
            if skipped_conflicts > 0:
                messages.warning(
                    request, 
                    f"Set {created_count} available slots, but skipped {skipped_conflicts} date(s) where you are already contractually committed to a 24-hour live-in active care assignment."
                )
            else:
                messages.success(request, f"✅ Successfully added {created_count} new availability slot(s)!")

            return redirect("requests:availability_list")

        except Exception as e:
            messages.error(request, f"Error processing availability: {str(e)}")
            return redirect("requests:set_availability")

    # Fetch existing to show the user
    existing_slots = CaretakerAvailability.objects.filter(
        caretaker=request.user,
        date__gte=date.today(),
        status="available"
    ).order_by("date", "start_time")

    today = date.today()
    start_date = today + timedelta(days=1)
    next_30_days = [(start_date + timedelta(days=i)) for i in range(30)]

    context = {
        "existing_slots": existing_slots,
        "existing_availability": existing_slots,
        "next_30_days": next_30_days,
        "today": today.strftime("%Y-%m-%d"),
        "tomorrow": start_date.strftime("%Y-%m-%d"),
    }
    return render(request, "requests/set_availability.html", context)


@login_required
@require_POST
def delete_availability(request, availability_id):
    """Delete an availability slot"""
    try:
        availability = get_object_or_404(CaretakerAvailability, id=availability_id, caretaker=request.user)
        
        if availability.status == 'booked':
            messages.error(request, "Cannot delete a booked slot. Please contact the family to cancel the booking first.")
            return redirect('requests:availability_list')
        
        existing_booking = CareBooking.objects.filter(
            caretaker=request.user,
            booking_date=availability.date,
            start_time=availability.start_time,
            status__in=['pending', 'confirmed', 'in_progress']
        ).exists()
        
        if existing_booking:
            messages.error(request, "Cannot delete a slot that has active bookings.")
            return redirect('requests:availability_list')
        
        availability.delete()
        messages.success(request, "Availability slot deleted successfully!")
        
    except Exception as e:
        messages.error(request, f"Error deleting availability: {str(e)}")
    
    return redirect('requests:availability_list')


@login_required
@require_POST
def clear_all_availability(request):
    """Clear all availability slots for the current caretaker"""
    if request.user.role != "caretaker":
        messages.error(request, "Access denied.")
        return redirect("users:index")
    
    try:
        caretaker_profile = CaretakerProfile.objects.get(user=request.user)
    except CaretakerProfile.DoesNotExist:
        messages.error(request, "Caretaker profile not found.")
        return redirect("requests:availability_list")
    
    slots = CaretakerAvailability.objects.filter(caretaker=caretaker_profile)
    count = slots.count()
    
    if count > 0:
        slots.delete()
        messages.success(request, f"✅ Successfully cleared {count} recurring availability slot(s). Your weekly schedule has been removed.")
    else:
        messages.warning(request, "No recurring availability slots found to clear.")
    
    return redirect('requests:availability_list')