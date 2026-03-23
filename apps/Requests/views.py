from datetime import datetime, timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q
from django.core.paginator import Paginator
from django.views.decorators.http import require_POST

from apps.Applications.models import CareApplication
from .models import CareRequest, CaretakerAvailability, CareBooking
from apps.Users.models import User, CaretakerProfile


# ============================================================================
# FAMILY VIEWS - Find & Book Caretakers
# ============================================================================


# ----------------------------------------------------------------------------
# Find caretakers (for family members)
# ----------------------------------------------------------------------------
@login_required
def find_caretakers(request):
    caretakers = CaretakerProfile.objects.all()

    # Get filter parameters from request
    q = request.GET.get("q")
    experience = request.GET.get("experience")
    availability = request.GET.get("availability")

    # Apply filters
    if q:
        # Search across multiple fields including location
        caretakers = caretakers.filter(
            Q(user__first_name__icontains=q) |
            Q(user__last_name__icontains=q) |
            Q(qualification__icontains=q) |
            Q(city__icontains=q) |
            Q(state__icontains=q) |
            Q(address__icontains=q) |
            Q(skills__icontains=q) |
            Q(pincode__icontains=q)
        )

    if experience:
        caretakers = caretakers.filter(experience_years__gte=experience)

    if availability:
        caretakers = caretakers.filter(availability_status=availability)

    context = {"caretakers": caretakers}
    return render(request, "users/search_caretakers.html", context)




# ============================================================================
# CARETAKER VIEWS - Browse & Apply to Requests
# ============================================================================

# ----------------------------------------------------------------------------
# Browse open requests (for caretakers)
# ----------------------------------------------------------------------------
@login_required
def browse_requests(request):
    """Browse all open care requests (for caretakers)"""

    # Check if user is caretaker
    if request.user.role != "caretaker":
        messages.error(request, "Access denied. This page is for caretakers only.")
        return redirect("index")

    # Get open requests
    requests_list = CareRequest.objects.filter(status="open").order_by("-created_at")

    # Get IDs of requests already applied
    applied_request_ids = CareApplication.objects.filter(
        caretaker=request.user
    ).values_list("request_id", flat=True)

    # Filter by search
    search = request.GET.get("search")
    if search:
        requests_list = requests_list.filter(
            Q(patient_name__icontains=search)
            | Q(city__icontains=search)
            | Q(medical_condition__icontains=search)
        )

    # Filter by care type
    care_type = request.GET.get("care_type")
    if care_type:
        requests_list = requests_list.filter(care_type=care_type)

    # Pagination
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


# ----------------------------------------------------------------------------
# Apply for a request (for caretakers)
# ----------------------------------------------------------------------------
@login_required
def apply_for_request(request, request_id):
    """Apply for a care request (for caretakers)"""
    if request.user.role != "caretaker":
        messages.error(request, "❌ Access denied.")
        return redirect("index")

    if not request.user.is_verified:
        messages.warning(
            request, "⚠️ Please complete your verification before applying."
        )
        return redirect("verification_pending")

    care_request = get_object_or_404(CareRequest, id=request_id, status="open")

    # Check if request is still available
    if not care_request.can_apply():
        messages.error(request, "❌ This request is no longer accepting applications.")
        return redirect("request_detail", request_id=care_request.id)

    # Check if already applied
    if CareApplication.objects.filter(
        request=care_request, caretaker=request.user
    ).exists():
        messages.warning(request, "⚠️ You have already applied for this request.")
        return redirect("request_detail", request_id=care_request.id)

    # Create a temporary application object to check availability
    temp_application = CareApplication(
        caretaker=request.user,
        request=care_request,
        job_type=care_request.care_type,
    )

    # Check caretaker availability before showing form
    is_available, availability_reason, _ = (
        temp_application.check_caretaker_availability()
    )
    if not is_available:
        messages.error(request, f"❌ {availability_reason}")
        return redirect("browse_requests")

    if request.method == "POST":
        message = request.POST.get("message", "").strip()
        proposed_rate = request.POST.get("proposed_rate")
        job_type = request.POST.get("job_type", care_request.care_type)

        # Part-time specific fields
        work_start_time = request.POST.get("work_start_time")
        work_end_time = request.POST.get("work_end_time")
        work_days = request.POST.getlist("work_days")

        # Validate required fields
        if not message or not proposed_rate:
            messages.error(request, "❌ All fields are required.")
            return render(
                request,
                "requests/apply_for_request.html",
                {"care_request": care_request, "job_type": job_type},
            )

        # For part-time, validate time inputs
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

            # Convert work_days to integers
            try:
                work_days = [int(day) for day in work_days]
            except (ValueError, TypeError):
                messages.error(request, "❌ Invalid work days selected.")
                return render(
                    request,
                    "requests/apply_for_request.html",
                    {"care_request": care_request},
                )

        # Double-check availability before creating
        temp_app = CareApplication(
            caretaker=request.user,
            request=care_request,
            job_type=job_type,
            work_start_time=work_start_time if job_type != "full_time" else None,
            work_end_time=work_end_time if job_type != "full_time" else None,
            work_days=work_days if job_type != "full_time" else None,
        )

        is_available, availability_reason, _ = temp_app.check_caretaker_availability()
        if not is_available:
            messages.error(request, f"❌ {availability_reason}")
            return redirect("browse_requests")

        try:
            # Create application
            application = CareApplication.objects.create(
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
            return redirect("my_applications")

        except Exception as e:
            messages.error(request, f"❌ Error submitting application: {str(e)}")
            return render(
                request,
                "requests/apply_for_request.html",
                {"care_request": care_request},
            )

    # GET request - show application form
    context = {
        "care_request": care_request,
        "job_type": care_request.care_type,
        "DAYS_OF_WEEK": CareApplication.DAYS_OF_WEEK,
    }
    return render(request, "requests/apply_for_request.html", context)


# ============================================================================
# FAMILY VIEWS - Request Management
# ============================================================================


# ----------------------------------------------------------------------------
# Post a new care request (for families)
# ----------------------------------------------------------------------------
@login_required
def post_request(request):
    """Post a new care request (for families)"""
    if request.user.role != "family":
        messages.error(request, "Only family members can post care requests.")
        return redirect("index")

    # Define all choices for dropdowns
    gender_choices = [
        ("male", "Male"),
        ("female", "Female"),
        ("other", "Other"),
    ]

    mobility_choices = [
        ("independent", "Independent"),
        ("walker", "Walker/Cane"),
        ("wheelchair", "Wheelchair"),
        ("bedridden", "Bedridden"),
    ]

    cognitive_choices = [
        ("normal", "Normal"),
        ("mild_impairment", "Mild Cognitive Impairment"),
        ("dementia", "Dementia"),
        ("alzheimers", "Alzheimer's"),
    ]

    care_type_choices = [
        ("full_time", "Full Time"),
        ("part_time", "Part Time"),
        ("night_care", "Night Care"),
        ("home_visit", "Home Visit"),
        ("emergency", "Emergency Care"),
        ("respite", "Respite Care"),
        ("palliative", "Palliative Care"),
        ("post_surgery", "Post-Surgery Care"),
    ]

    urgency_choices = [
        ("low", "Low - Can wait"),
        ("medium", "Medium - Within a week"),
        ("high", "High - Within 2-3 days"),
        ("urgent", "Urgent - Immediately"),
    ]

    payment_choices = [
        ("hourly", "Per Hour"),
        ("daily", "Per Day"),
        ("weekly", "Per Week"),
        ("monthly", "Per Month"),
    ]

    interview_choices = [
        ("in_person", "In Person"),
        ("video", "Video Call"),
        ("phone", "Phone Call"),
    ]

    if request.method == "POST":
        try:
            # Convert and validate fields
            patient_age = int(request.POST.get("patient_age"))
            duration_days = int(request.POST.get("duration_days"))
            salary_offered = float(request.POST.get("salary_offered"))
            days_per_week = int(request.POST.get("days_per_week", 7))

            # Parse date
            start_date = request.POST.get("start_date")
            if isinstance(start_date, str):
                start_date = datetime.strptime(start_date, "%Y-%m-%d").date()

            # Validate start date
            if start_date < timezone.now().date():
                messages.error(request, "Start date cannot be in the past.")
                return render(
                    request,
                    "requests/post_care_request.html",
                    {
                        "gender_choices": gender_choices,
                        "mobility_choices": mobility_choices,
                        "cognitive_choices": cognitive_choices,
                        "care_type_choices": care_type_choices,
                        "urgency_choices": urgency_choices,
                        "payment_choices": payment_choices,
                        "interview_choices": interview_choices,
                        "form_data": request.POST,
                    },
                )

            # Create the request
            care_request = CareRequest(
                family=request.user,
                patient_name=request.POST.get("patient_name"),
                patient_age=patient_age,
                patient_gender=request.POST.get("patient_gender"),
                medical_condition=request.POST.get("medical_condition"),
                mobility_status=request.POST.get("mobility_status", "independent"),
                cognitive_status=request.POST.get("cognitive_status", "normal"),
                care_type=request.POST.get("care_type"),
                urgency_level=request.POST.get("urgency_level", "medium"),
                required_skills=request.POST.get("required_skills", ""),
                preferred_qualifications=request.POST.get(
                    "preferred_qualifications", ""
                ),
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
                accommodation_provided=request.POST.get("accommodation_provided")
                == "on",
                accommodation_details=request.POST.get("accommodation_details", ""),
                interview_required=request.POST.get("interview_required") == "on",
                interview_type=request.POST.get("interview_type", "video"),
                status="draft",
            )

            care_request.save()
            messages.success(
                request, "Care request created successfully! You can now publish it."
            )
            return redirect("request_detail", request_id=care_request.id)

        except ValueError as e:
            messages.error(request, f"Invalid data format: {str(e)}")
        except Exception as e:
            messages.error(request, f"Error creating request: {str(e)}")

    return render(
        request,
        "requests/post_care_request.html",
        {
            "gender_choices": gender_choices,
            "mobility_choices": mobility_choices,
            "cognitive_choices": cognitive_choices,
            "care_type_choices": care_type_choices,
            "urgency_choices": urgency_choices,
            "payment_choices": payment_choices,
            "interview_choices": interview_choices,
        },
    )


# ----------------------------------------------------------------------------
# Publish a draft request (for families)
# ----------------------------------------------------------------------------
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
        messages.success(
            request, "Request published successfully! It is now visible to caregivers."
        )
    else:
        messages.error(request, "Only draft requests can be published.")

    return redirect("request_detail", request_id=care_request.id)


# ----------------------------------------------------------------------------
# View my posted requests (for families)
# ----------------------------------------------------------------------------
@login_required
def my_requests(request):
    """View my posted requests (for families)"""
    if request.user.role != "family":
        messages.error(request, "Access denied.")
        return redirect("index")

    requests_list = CareRequest.objects.filter(family=request.user)

    # Filter by status
    status = request.GET.get("status")
    if status and status != "all":
        requests_list = requests_list.filter(status=status)

    # Search
    search = request.GET.get("search")
    if search:
        requests_list = requests_list.filter(
            Q(patient_name__icontains=search)
            | Q(medical_condition__icontains=search)
            | Q(city__icontains=search)
        )

    # Add application counts to each request
    for req in requests_list:
        req.total_applications = CareApplication.objects.filter(request=req).count()
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

    # Order by most recent
    requests_list = requests_list.order_by("-created_at")

    # Calculate counts for summary stats
    open_count = requests_list.filter(status="open").count()
    draft_count = requests_list.filter(status="draft").count()
    assigned_count = requests_list.filter(status="assigned").count()
    closed_count = requests_list.filter(status="closed").count()

    # Pagination
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


# ----------------------------------------------------------------------------
# View details of a specific request
# ----------------------------------------------------------------------------
@login_required
def request_detail(request, request_id):
    """View details of a specific request"""
    care_request = get_object_or_404(CareRequest, id=request_id)

    # Check permissions
    if request.user.role == "family" and care_request.family != request.user:
        messages.error(request, "You do not have permission to view this request.")
        return redirect("index")

    # Check if current user has already applied (for caretakers)
    has_applied = False
    if request.user.role == "caretaker":
        has_applied = CareApplication.objects.filter(
            caretaker=request.user, request=care_request
        ).exists()

    # Get application counts
    from django.db.models import Count

    application_stats = CareApplication.objects.filter(request=care_request).aggregate(
        total=Count("id"),
        pending=Count("id", filter=Q(status="pending")),
        shortlisted=Count("id", filter=Q(status="shortlisted")),
        accepted=Count("id", filter=Q(status="accepted")),
        rejected=Count("id", filter=Q(status="rejected")),
    )

    context = {
        "care_request": care_request,
        "user": request.user,
        "has_applied": has_applied,
        "application_stats": application_stats,
    }
    return render(request, "requests/request_detail.html", context)


# ----------------------------------------------------------------------------
# Edit a care request (for families)
# ----------------------------------------------------------------------------
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
        return redirect("request_detail", request_id=care_request.id)

    if request.method == "POST":
        try:
            action = request.POST.get("action", "")

            # Update fields
            care_request.patient_name = request.POST.get(
                "patient_name", care_request.patient_name
            )

            patient_age = request.POST.get("patient_age")
            if patient_age:
                care_request.patient_age = int(patient_age)

            patient_gender = request.POST.get("patient_gender")
            if patient_gender:
                care_request.patient_gender = patient_gender

            care_request.medical_condition = request.POST.get(
                "medical_conditions", care_request.medical_condition
            )
            care_request.mobility_status = request.POST.get(
                "mobility_status", care_request.mobility_status
            )
            care_request.cognitive_status = request.POST.get(
                "cognitive_status", care_request.cognitive_status
            )
            care_request.care_type = request.POST.get(
                "care_type", care_request.care_type
            )
            care_request.urgency_level = request.POST.get(
                "urgency_level", care_request.urgency_level
            )

            salary = request.POST.get("salary_offered")
            if salary:
                care_request.salary_offered = float(salary)

            care_request.payment_frequency = request.POST.get(
                "payment_frequency", care_request.payment_frequency
            )
            care_request.negotiable = request.POST.get("negotiable") == "on"

            start_date = request.POST.get("start_date")
            if start_date:
                care_request.start_date = datetime.strptime(
                    start_date, "%Y-%m-%d"
                ).date()

            shift_timing = request.POST.get("shift_timing")
            if shift_timing:
                care_request.shift_timing = shift_timing

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
            care_request.gender_preference = request.POST.get(
                "gender_preference", care_request.gender_preference
            )

            age_min = request.POST.get("age_preference_min")
            if age_min:
                care_request.age_preference_min = int(age_min)

            age_max = request.POST.get("age_preference_max")
            if age_max:
                care_request.age_preference_max = int(age_max)

            care_request.language_preference = request.POST.get(
                "language_preference", care_request.language_preference
            )
            care_request.required_skills = request.POST.get(
                "required_skills", care_request.required_skills
            )
            care_request.preferred_qualifications = request.POST.get(
                "preferred_qualifications", care_request.preferred_qualifications
            )
            care_request.special_requirements = request.POST.get(
                "special_requirements", care_request.special_requirements
            )
            care_request.equipment_provided = request.POST.get(
                "equipment_provided", care_request.equipment_provided
            )
            care_request.accommodation_provided = (
                request.POST.get("accommodation_provided") == "on"
            )
            care_request.accommodation_details = request.POST.get(
                "accommodation_details", care_request.accommodation_details
            )
            care_request.interview_required = (
                request.POST.get("interview_required") == "on"
            )
            care_request.interview_type = request.POST.get(
                "interview_type", care_request.interview_type
            )
            care_request.emergency_contact_name = request.POST.get(
                "emergency_contact_name", care_request.emergency_contact_name
            )
            care_request.emergency_contact_phone = request.POST.get(
                "emergency_contact_phone", care_request.emergency_contact_phone
            )
            care_request.care_details = request.POST.get(
                "care_details", care_request.care_details
            )

            if action == "publish" and care_request.status == "draft":
                care_request.publish()
                messages.success(request, "✅ Request published successfully!")
                return redirect("request_detail", request_id=care_request.id)
            elif action == "save_draft":
                care_request.status = "draft"
                care_request.save()
                messages.success(request, "✅ Draft saved successfully!")
                return redirect("my_requests")
            else:
                care_request.save()
                messages.success(request, "✅ Request updated successfully!")
                return redirect("request_detail", request_id=care_request.id)

        except ValueError as e:
            messages.error(request, f"❌ Invalid data format: {str(e)}")
        except Exception as e:
            messages.error(request, f"❌ Error updating request: {str(e)}")

    applications_count = CareApplication.objects.filter(request=care_request).count()
    pending_count = CareApplication.objects.filter(
        request=care_request, status="pending"
    ).count()
    shortlisted_count = CareApplication.objects.filter(
        request=care_request, status="shortlisted"
    ).count()
    offers_sent_count = CareApplication.objects.filter(
        request=care_request,
        status__in=["offer_sent", "offer_accepted", "offer_declined"],
    ).count()

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


# ----------------------------------------------------------------------------
# Close or reopen a care request (for families)
# ----------------------------------------------------------------------------
@login_required
def close_request(request, request_id):
    """Close or reopen a care request (for families)"""
    if request.user.role != "family":
        messages.error(
            request, "❌ Access denied. Only family members can perform this action."
        )
        return redirect("index")

    care_request = get_object_or_404(CareRequest, id=request_id, family=request.user)

    if request.method == "POST":
        try:
            if care_request.status == "open":
                care_request.status = "closed"
                care_request.closed_at = timezone.now()
                CareApplication.objects.filter(
                    request=care_request, status="pending"
                ).update(status="rejected", rejection_note="Request closed by family")
                care_request.save()
                messages.success(
                    request,
                    f"✅ Request for {care_request.patient_name} has been closed successfully.",
                )
            elif care_request.status == "closed":
                if care_request.assigned_caretaker:
                    messages.error(
                        request,
                        "❌ Cannot reopen a request that has an assigned caretaker.",
                    )
                    return redirect("request_detail", request_id=care_request.id)
                care_request.status = "open"
                care_request.closed_at = None
                care_request.save()
                messages.success(
                    request,
                    f"✅ Request for {care_request.patient_name} has been reopened successfully.",
                )
            else:
                messages.error(
                    request,
                    f"❌ Cannot close a request with status: {care_request.get_status_display()}",
                )
                return redirect("request_detail", request_id=care_request.id)
        except Exception as e:
            messages.error(request, f"❌ Error closing request: {str(e)}")

    return redirect("request_detail", request_id=care_request.id)


# ----------------------------------------------------------------------------
# Delete a care request (for families)
# ----------------------------------------------------------------------------
@login_required
def delete_request(request, request_id):
    care_request = get_object_or_404(CareRequest, id=request_id, family=request.user)

    if request.method == "POST":
        if care_request.status not in ["draft", "closed", "open"]:
            messages.error(
                request, f"❌ Only draft, open, or closed requests can be deleted."
            )
            return redirect("request_detail", request_id=care_request.id)

        patient_name = care_request.patient_name
        care_request.delete()
        messages.success(
            request,
            f"✅ Care request for {patient_name} has been deleted successfully.",
        )
        return redirect("my_requests")

    return render(
        request, "requests/delete_request_confirm.html", {"request_obj": care_request}
    )


# ----------------------------------------------------------------------------
# Save draft without publishing (for families)
# ----------------------------------------------------------------------------
@login_required
def save_draft(request, request_id):
    """Save draft without publishing (for families)"""
    if request.user.role != "family":
        messages.error(request, "❌ Access denied.")
        return redirect("index")

    care_request = get_object_or_404(CareRequest, id=request_id, family=request.user)

    if not care_request.can_edit():
        messages.error(request, "❌ Only draft requests can be saved as draft.")
        return redirect("request_detail", request_id=care_request.id)

    if request.method == "POST":
        try:
            # Update all fields (similar to edit but set status to draft)
            care_request.patient_name = request.POST.get(
                "patient_name", care_request.patient_name
            )
            patient_age = request.POST.get("patient_age")
            if patient_age:
                care_request.patient_age = int(patient_age)
            # ... (update other fields similar to edit_request)
            care_request.status = "draft"
            care_request.save()
            messages.success(
                request, "✅ Draft saved successfully! You can continue editing later."
            )
        except Exception as e:
            messages.error(request, f"❌ Error saving draft: {str(e)}")

        return redirect("my_requests")

    return redirect("request_detail", request_id=care_request.id)



@login_required
def caretaker_detail(request, caretaker_id):
    """View detailed profile of a caretaker"""
    from apps.Users.models import CaretakerProfile
    
    caretaker = get_object_or_404(CaretakerProfile, id=caretaker_id)
    
    # Get upcoming bookings (if user is family)
    upcoming_bookings = None
    if request.user.role == 'family':
        upcoming_bookings = CareBooking.objects.filter(
            caretaker=caretaker.user,
            family=request.user,
            status__in=['pending', 'confirmed'],
            booking_date__gte=timezone.now().date()
        ).order_by('booking_date')[:5]
    
    # Get reviews/ratings
    reviews = None  # Add your review model if you have one
    
    context = {
        'caretaker': caretaker,
        'upcoming_bookings': upcoming_bookings,
        'reviews': reviews,
    }
    return render(request, 'requests/caretaker_detail.html', context)


# ============================================================================
# BOOKING & AVAILABILITY VIEWS
# ============================================================================


@login_required
def view_caretaker_availability(request, caretaker_id):
    """View a caretaker's availability calendar"""
    caretaker = get_object_or_404(User, id=caretaker_id, role="caretaker")
    caretaker_profile = get_object_or_404(CaretakerProfile, user=caretaker)

    import calendar
    from datetime import date, timedelta

    year = int(request.GET.get("year", date.today().year))
    month = int(request.GET.get("month", date.today().month))

    first_day = date(year, month, 1)
    if month == 12:
        last_day = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        last_day = date(year, month + 1, 1) - timedelta(days=1)

    availabilities = CaretakerAvailability.objects.filter(
        caretaker=caretaker, date__gte=first_day, date__lte=last_day, status="available"
    ).order_by("date", "start_time")

    availability_by_date = {}
    for avail in availabilities:
        if avail.date not in availability_by_date:
            availability_by_date[avail.date] = []
        availability_by_date[avail.date].append(avail)

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

    cal = calendar.monthcalendar(year, month)
    month_name = calendar.month_name[month]

    context = {
        "caretaker": caretaker,
        "caretaker_profile": caretaker_profile,
        "year": year,
        "month": month,
        "month_name": month_name,
        "calendar": cal,
        "availability_by_date": availability_by_date,
        "prev_year": prev_year,
        "prev_month": prev_month,
        "next_year": next_year,
        "next_month": next_month,
    }
    return render(request, "requests/caretaker_availability.html", context)


@login_required
def book_caretaker(request, caretaker_id, request_id):
    """Book a caretaker for a specific care request"""
    if request.user.role != "family":
        messages.error(request, "Only family members can book caretakers")
        return redirect("index")

    care_request = get_object_or_404(CareRequest, id=request_id, family=request.user)
    caretaker = get_object_or_404(User, id=caretaker_id, role="caretaker")

    if care_request.status != "open":
        messages.error(request, "This care request is no longer available for booking")
        return redirect("request_detail", request_id=care_request.id)

    selected_date = request.GET.get("date")
    selected_start = request.GET.get("start")
    selected_end = request.GET.get("end")

    if request.method == "POST":
        booking_date = request.POST.get("booking_date")
        start_time = request.POST.get("start_time")
        end_time = request.POST.get("end_time")
        family_notes = request.POST.get("family_notes", "")

        if not all([booking_date, start_time, end_time]):
            messages.error(request, "Please fill all required fields")
            return redirect(
                "book_caretaker", caretaker_id=caretaker_id, request_id=request_id
            )

        try:
            booking_date_obj = datetime.strptime(booking_date, "%Y-%m-%d").date()
            start_time_obj = datetime.strptime(start_time, "%H:%M").time()
            end_time_obj = datetime.strptime(end_time, "%H:%M").time()

            start_datetime = datetime.combine(booking_date_obj, start_time_obj)
            end_datetime = datetime.combine(booking_date_obj, end_time_obj)
            duration_hours = (end_datetime - start_datetime).seconds / 3600

            availability = CaretakerAvailability.objects.filter(
                caretaker=caretaker,
                date=booking_date_obj,
                start_time__lte=start_time_obj,
                end_time__gte=end_time_obj,
                status="available",
            ).first()

            if not availability:
                messages.error(request, "The selected time slot is not available")
                return redirect("caretaker_availability", caretaker_id=caretaker_id)

            existing_booking = CareBooking.objects.filter(
                caretaker=caretaker,
                booking_date=booking_date_obj,
                start_time=start_time_obj,
                status__in=["pending", "confirmed", "in_progress"],
            ).exists()

            if existing_booking:
                messages.error(request, "This time slot is already booked")
                return redirect("caretaker_availability", caretaker_id=caretaker_id)

            booking = CareBooking.objects.create(
                care_request=care_request,
                caretaker=caretaker,
                family=request.user,
                booking_date=booking_date_obj,
                start_time=start_time_obj,
                end_time=end_time_obj,
                duration_hours=duration_hours,
                status="pending",
                family_notes=family_notes,
            )

            from apps.Notifications.models import Notification

            Notification.objects.create(
                recipient=caretaker,
                sender=request.user,
                notification_type="booking",
                title="New Booking Request",
                message=f"{request.user.get_full_name()} has requested a booking for {booking_date} at {start_time}",
                icon="fa-calendar-plus",
                link=f"/bookings/{booking.id}/",
                is_read=False,
            )

            messages.success(request, "Booking request sent successfully!")
            return redirect("my_bookings")

        except Exception as e:
            messages.error(request, f"Error creating booking: {str(e)}")

    context = {
        "care_request": care_request,
        "caretaker": caretaker,
        "selected_date": selected_date,
        "selected_start": selected_start,
        "selected_end": selected_end,
    }
    return render(request, "requests/book_caretaker.html", context)


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
    }
    return render(request, "requests/booking_detail.html", context)


@login_required
@require_POST
def confirm_booking(request, booking_id):
    """Confirm a booking (caretaker action)"""
    booking = get_object_or_404(CareBooking, id=booking_id, caretaker=request.user)

    if booking.status != "pending":
        messages.error(request, "This booking cannot be confirmed")
        return redirect("booking_detail", booking_id=booking.id)

    if booking.confirm_booking():
        from apps.Notifications.models import Notification

        Notification.objects.create(
            recipient=booking.family,
            sender=request.user,
            notification_type="booking",
            title="Booking Confirmed",
            message=f"{request.user.get_full_name()} has confirmed your booking for {booking.booking_date}",
            icon="fa-calendar-check",
            link=f"/bookings/{booking.id}/",
            is_read=False,
        )
        messages.success(request, "Booking confirmed successfully!")
    else:
        messages.error(request, "Failed to confirm booking")

    return redirect("booking_detail", booking_id=booking.id)


@login_required
@require_POST
def cancel_booking(request, booking_id):
    """Cancel a booking"""
    booking = get_object_or_404(CareBooking, id=booking_id)

    if request.user != booking.family and request.user != booking.caretaker:
        messages.error(request, "Access denied")
        return redirect("index")

    if booking.status in ["completed", "cancelled"]:
        messages.error(request, "This booking cannot be cancelled")
        return redirect("booking_detail", booking_id=booking.id)

    if booking.cancel_booking():
        from apps.Notifications.models import Notification

        recipient = (
            booking.family if request.user == booking.caretaker else booking.caretaker
        )
        Notification.objects.create(
            recipient=recipient,
            sender=request.user,
            notification_type="booking",
            title="Booking Cancelled",
            message=f"{request.user.get_full_name()} has cancelled the booking for {booking.booking_date}",
            icon="fa-calendar-times",
            link=f"/bookings/{booking.id}/",
            is_read=False,
        )
        messages.success(request, "Booking cancelled successfully!")
    else:
        messages.error(request, "Failed to cancel booking")

    return redirect("booking_detail", booking_id=booking.id)


@login_required
def start_booking(request, booking_id):
    """Start a booking (mark as in progress)"""
    booking = get_object_or_404(CareBooking, id=booking_id)

    if request.user != booking.caretaker:
        messages.error(request, "Only the caretaker can start a booking")
        return redirect("booking_detail", booking_id=booking.id)

    if booking.status != "confirmed":
        messages.error(request, "This booking cannot be started")
        return redirect("booking_detail", booking_id=booking.id)

    booking.status = "in_progress"
    booking.save()

    from apps.Notifications.models import Notification

    Notification.objects.create(
        recipient=booking.family,
        sender=request.user,
        notification_type="booking",
        title="Care Session Started",
        message=f"{request.user.get_full_name()} has started the care session",
        icon="fa-play-circle",
        link=f"/bookings/{booking.id}/",
        is_read=False,
    )

    messages.success(request, "Care session started!")
    return redirect("booking_detail", booking_id=booking.id)


@login_required
def complete_booking(request, booking_id):
    """Complete a booking"""
    booking = get_object_or_404(CareBooking, id=booking_id)

    if request.user != booking.caretaker:
        messages.error(request, "Only the caretaker can complete a booking")
        return redirect("booking_detail", booking_id=booking.id)

    if booking.status != "in_progress":
        messages.error(request, "This booking cannot be completed")
        return redirect("booking_detail", booking_id=booking.id)

    if booking.complete_booking():
        from apps.Notifications.models import Notification

        Notification.objects.create(
            recipient=booking.family,
            sender=request.user,
            notification_type="booking",
            title="Care Session Completed",
            message=f"{request.user.get_full_name()} has completed the care session",
            icon="fa-check-circle",
            link=f"/bookings/{booking.id}/",
            is_read=False,
        )
        messages.success(request, "Care session completed!")
    else:
        messages.error(request, "Failed to complete booking")

    return redirect("booking_detail", booking_id=booking.id)


@login_required
def caretaker_set_availability(request):
    """Set availability for caretaker"""
    if request.user.role != "caretaker":
        messages.error(request, "Only caretakers can set availability")
        return redirect("index")

    if request.method == "POST":
        dates = request.POST.getlist("dates")
        start_time = request.POST.get("start_time")
        end_time = request.POST.get("end_time")
        is_recurring = request.POST.get("is_recurring") == "on"
        recurring_until = request.POST.get("recurring_until")

        if not dates or not start_time or not end_time:
            messages.error(request, "Please fill all required fields")
            return redirect("caretaker_set_availability")

        try:
            start_time_obj = datetime.strptime(start_time, "%H:%M").time()
            end_time_obj = datetime.strptime(end_time, "%H:%M").time()

            recurring_until_date = None
            if recurring_until and is_recurring:
                recurring_until_date = datetime.strptime(
                    recurring_until, "%Y-%m-%d"
                ).date()

            created_count = 0

            for date_str in dates:
                date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()

                existing = CaretakerAvailability.objects.filter(
                    caretaker=request.user, date=date_obj, start_time=start_time_obj
                ).first()

                if existing:
                    existing.end_time = end_time_obj
                    existing.status = "available"
                    existing.is_recurring = is_recurring
                    existing.recurring_until = (
                        recurring_until_date if is_recurring else None
                    )
                    existing.save()
                else:
                    CaretakerAvailability.objects.create(
                        caretaker=request.user,
                        date=date_obj,
                        start_time=start_time_obj,
                        end_time=end_time_obj,
                        status="available",
                        is_recurring=is_recurring,
                        recurring_until=recurring_until_date if is_recurring else None,
                    )
                created_count += 1

            messages.success(
                request, f"Successfully added {created_count} availability slots!"
            )
            return redirect("caretaker_availability_list")

        except Exception as e:
            messages.error(request, f"Error setting availability: {str(e)}")

    context = {
        "next_7_days": [(datetime.now().date() + timedelta(days=i)) for i in range(7)],
    }
    return render(request, "requests/set_availability.html", context)


@login_required
def caretaker_availability_list(request):
    """View all availability slots for caretaker"""
    if request.user.role != "caretaker":
        messages.error(request, "Access denied")
        return redirect("index")

    availabilities = CaretakerAvailability.objects.filter(
        caretaker=request.user
    ).order_by("-date", "start_time")

    status_filter = request.GET.get("status")
    if status_filter and status_filter != "all":
        availabilities = availabilities.filter(status=status_filter)

    paginator = Paginator(availabilities, 20)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "availabilities": page_obj,
        "status_filter": status_filter,
    }
    return render(request, "requests/availability_list.html", context)


@login_required
@require_POST
def delete_availability(request, availability_id):
    """Delete an availability slot"""
    availability = get_object_or_404(
        CaretakerAvailability, id=availability_id, caretaker=request.user
    )

    if availability.status == "booked":
        messages.error(request, "Cannot delete a booked slot")
        return redirect("caretaker_availability_list")

    availability.delete()
    messages.success(request, "Availability slot deleted successfully!")
    return redirect("caretaker_availability_list")
