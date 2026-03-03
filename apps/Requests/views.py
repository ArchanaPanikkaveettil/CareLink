from datetime import datetime, timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q
from django.core.paginator import Paginator

from apps.Applications.models import CareApplication
from .models import CareRequest
from apps.Users.models import User, CaretakerProfile


# ============================================================================
# CARETAKER VIEWS
# ============================================================================

# ----------------------------------------------------------------------------
# Browse open requests (for caretakers)
# ----------------------------------------------------------------------------
@login_required
def browse_requests(request):
    """Browse all open care requests (for caretakers)"""
    if request.user.role != 'caretaker':
        messages.error(request, 'Access denied.')
        return redirect('index')
    
    requests = CareRequest.objects.filter(status="open").order_by('-created_at')
    
    # Get IDs of requests already applied
    applied_request_ids = CareApplication.objects.filter(
        caretaker=request.user
    ).values_list("request_id", flat=True)
    
    # Filter by search
    search = request.GET.get('search')
    if search:
        requests = requests.filter(
            Q(patient_name__icontains=search) |
            Q(city__icontains=search) |
            Q(medical_condition__icontains=search)
        )
    
    # Filter by care type
    care_type = request.GET.get('care_type')
    if care_type:
        requests = requests.filter(care_type=care_type)
    
    # Pagination
    paginator = Paginator(requests, 10)  # Show 10 requests per page
    page_number = request.GET.get('page')
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
# ----------------------------------------------------------------------------
@login_required
def apply_for_request(request, request_id):
    """Apply for a care request (for caretakers)"""
    if request.user.role != "caretaker":
        messages.error(request, "❌ Access denied.")
        return redirect("index")

    if not request.user.is_verified:
        messages.warning(request, "⚠️ Please complete your verification before applying.")
        return redirect("verification_pending")

    care_request = get_object_or_404(
        CareRequest,
        id=request_id,
        status="open"
    )

    # Check if request is still available
    if not care_request.can_apply():
        messages.error(request, "❌ This request is no longer accepting applications.")
        return redirect("request_detail", request_id=care_request.id)

    # Check if already applied
    if CareApplication.objects.filter(
        request=care_request,
        caretaker=request.user
    ).exists():
        messages.warning(request, "⚠️ You have already applied for this request.")
        return redirect("request_detail", request_id=care_request.id)

    # Create a temporary application object to check availability
    temp_application = CareApplication(
        caretaker=request.user,
        request=care_request,
        job_type=care_request.care_type  # Use the request's care type
    )
    
    # Check caretaker availability before showing form
    is_available, availability_reason, _ = temp_application.check_caretaker_availability()
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
        work_days = request.POST.getlist("work_days")  # Multiple select for days

        # Validate required fields
        if not message or not proposed_rate:
            messages.error(request, "❌ All fields are required.")
            return render(request, "requests/apply_for_request.html", {
                "care_request": care_request,
                "job_type": job_type
            })

        # For part-time, validate time inputs
        if job_type in ['part_time', 'night_care', 'home_visit']:
            if not work_start_time or not work_end_time or not work_days:
                messages.error(request, "❌ Please specify working hours and days for part-time application.")
                return render(request, "requests/apply_for_request.html", {
                    "care_request": care_request,
                    "job_type": job_type
                })
            
            # Convert work_days to integers
            try:
                work_days = [int(day) for day in work_days]
            except (ValueError, TypeError):
                messages.error(request, "❌ Invalid work days selected.")
                return render(request, "requests/apply_for_request.html", {
                    "care_request": care_request
                })

        # Double-check availability before creating (in case something changed)
        temp_app = CareApplication(
            caretaker=request.user,
            request=care_request,
            job_type=job_type,
            work_start_time=work_start_time if job_type != 'full_time' else None,
            work_end_time=work_end_time if job_type != 'full_time' else None,
            work_days=work_days if job_type != 'full_time' else None
        )
        
        is_available, availability_reason, _ = temp_app.check_caretaker_availability()
        if not is_available:
            messages.error(request, f"❌ {availability_reason}")
            return redirect("browse_requests")

        try:
            # Create application with all fields
            application = CareApplication.objects.create(
                request=care_request,
                caretaker=request.user,
                message=message,
                proposed_rate=proposed_rate,
                status="pending",
                job_type=job_type,
                work_start_time=work_start_time if job_type != 'full_time' else None,
                work_end_time=work_end_time if job_type != 'full_time' else None,
                work_days=work_days if job_type != 'full_time' else None
            )

            messages.success(request, "✅ Application submitted successfully!")
            
            # TODO: Send notification to family
            # send_application_notification(application)
            
            return redirect("my_applications")
            
        except Exception as e:
            messages.error(request, f"❌ Error submitting application: {str(e)}")
            return render(request, "requests/apply_for_request.html", {
                "care_request": care_request
            })

    # GET request - show application form
    context = {
        "care_request": care_request,
        "job_type": care_request.care_type,  # Pre-select based on request type
        "DAYS_OF_WEEK": CareApplication.DAYS_OF_WEEK,  # Pass day choices to template
    }
    return render(request, "requests/apply_for_request.html", context)


# ============================================================================
# FAMILY VIEWS
# ============================================================================

# ----------------------------------------------------------------------------
# Post a new care request (for families)
# ----------------------------------------------------------------------------
@login_required
def post_request(request):
    """Post a new care request (for families)"""
    if request.user.role != 'family':
        messages.error(request, 'Only family members can post care requests.')
        return redirect('index')
    
    if request.method == 'POST':
        try:
            # Convert and validate fields
            patient_age = int(request.POST.get('patient_age'))
            duration_days = int(request.POST.get('duration_days'))
            salary_offered = float(request.POST.get('salary_offered'))
            days_per_week = int(request.POST.get('days_per_week', 7))
            
            # Parse date
            start_date = request.POST.get('start_date')
            if isinstance(start_date, str):
                start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            
            # Validate start date is not in the past
            if start_date < timezone.now().date():
                messages.error(request, 'Start date cannot be in the past.')
                return render(request, 'requests/post_care_request.html')
            
            # Create the request
            care_request = CareRequest(
                family=request.user,
                
                # Patient Information
                patient_name=request.POST.get('patient_name'),
                patient_age=patient_age,
                patient_gender=request.POST.get('patient_gender'),
                medical_condition=request.POST.get('medical_condition'),
                
                # Medical Details
                mobility_status=request.POST.get('mobility_status', 'independent'),
                cognitive_status=request.POST.get('cognitive_status', 'normal'),
                
                # Care Requirements
                care_type=request.POST.get('care_type'),
                urgency_level=request.POST.get('urgency_level', 'medium'),
                
                # Skills
                required_skills=request.POST.get('required_skills', ''),
                preferred_qualifications=request.POST.get('preferred_qualifications', ''),
                
                # Compensation
                salary_offered=salary_offered,
                payment_frequency=request.POST.get('payment_frequency', 'monthly'),
                negotiable=request.POST.get('negotiable') == 'on',
                
                # Schedule
                shift_timing=request.POST.get('shift_timing', ''),
                start_date=start_date,
                duration_days=duration_days,
                
                # Working Hours
                hours_per_day=request.POST.get('hours_per_day') or None,
                days_per_week=days_per_week,
                
                # Preferences
                gender_preference=request.POST.get('gender_preference', 'any'),
                age_preference_min=request.POST.get('age_preference_min') or None,
                age_preference_max=request.POST.get('age_preference_max') or None,
                language_preference=request.POST.get('language_preference', ''),
                
                # Location
                address=request.POST.get('address'),
                city=request.POST.get('city', ''),
                state=request.POST.get('state', ''),
                pincode=request.POST.get('pincode', ''),
                landmark=request.POST.get('landmark', ''),
                
                # Additional
                special_requirements=request.POST.get('special_requirements', ''),
                equipment_provided=request.POST.get('equipment_provided', ''),
                
                # Accommodation
                accommodation_provided=request.POST.get('accommodation_provided') == 'on',
                accommodation_details=request.POST.get('accommodation_details', ''),
                
                # Interview
                interview_required=request.POST.get('interview_required') == 'on',
                interview_type=request.POST.get('interview_type', 'video'),
                
                # Status - start as draft, can be published later
                status='draft'
            )
            
            care_request.save()
            messages.success(request, 'Care request created successfully! You can now publish it.')
            return redirect('request_detail', request_id=care_request.id)
            
        except ValueError as e:
            messages.error(request, f'Invalid data format: {str(e)}')
            return render(request, 'requests/post_care_request.html')
        except Exception as e:
            messages.error(request, f'Error creating request: {str(e)}')
            return render(request, 'requests/post_care_request.html')
    
    return render(request, 'requests/post_care_request.html')


# ----------------------------------------------------------------------------
# Publish a draft request (for families)
# ----------------------------------------------------------------------------
@login_required
def publish_request(request, request_id):
    """Publish a draft request (for families)"""
    if request.user.role != 'family':
        messages.error(request, 'Access denied.')
        return redirect('index')
    
    care_request = get_object_or_404(CareRequest, id=request_id, family=request.user)
    
    if care_request.status == 'draft':
        care_request.status = 'open'
        care_request.published_at = timezone.now()
        care_request.save()
        messages.success(request, 'Request published successfully! It is now visible to caregivers.')
    else:
        messages.error(request, 'Only draft requests can be published.')
    
    return redirect('request_detail', request_id=care_request.id)


@login_required
# ----------------------------------------------------------------------------
# View my posted requests (for families)
# ----------------------------------------------------------------------------
@login_required
def my_requests(request):
    """View my posted requests (for families)"""
    if request.user.role != 'family':
        messages.error(request, 'Access denied.')
        return redirect('index')
    
    requests_list = CareRequest.objects.filter(family=request.user)
    
    # Filter by status
    status = request.GET.get('status')
    if status and status != 'all':
        requests_list = requests_list.filter(status=status)
    
    # Search
    search = request.GET.get('search')
    if search:
        requests_list = requests_list.filter(
            Q(patient_name__icontains=search) |
            Q(medical_condition__icontains=search) |
            Q(city__icontains=search)
        )
    
    # Add application counts to each request
    from apps.Applications.models import CareApplication
    
    for req in requests_list:
        # Total applications
        req.total_applications = CareApplication.objects.filter(request=req).count()
        
        # Shortlisted applications (including offers sent)
        req.shortlisted_applications = CareApplication.objects.filter(
            request=req, 
            status__in=['shortlisted', 'offer_sent', 'offer_accepted']
        ).count()
        
        # Pending applications
        req.pending_applications = CareApplication.objects.filter(
            request=req, 
            status='pending'
        ).count()
        
        # Offers sent
        req.offers_sent_count = CareApplication.objects.filter(
            request=req,
            status__in=['offer_sent', 'offer_accepted']
        ).count()
        
        # Check if request has any shortlisted
        req.has_active_shortlist = req.shortlisted_applications > 0
    
    # Order by most recent
    requests_list = requests_list.order_by('-created_at')
    
    # Calculate counts for summary stats
    open_count = requests_list.filter(status='open').count()
    draft_count = requests_list.filter(status='draft').count()
    assigned_count = requests_list.filter(status='assigned').count()
    closed_count = requests_list.filter(status='closed').count()
    
    # Pagination
    paginator = Paginator(requests_list, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'requests': page_obj,
        'status_filter': status,
        'search': search,
        'open_count': open_count,
        'draft_count': draft_count,
        'assigned_count': assigned_count,
        'closed_count': closed_count,
    }
    return render(request, 'requests/my_requests.html', context)




# ----------------------------------------------------------------------------
# View details of a specific request
# ----------------------------------------------------------------------------
@login_required
def request_detail(request, request_id):
    """View details of a specific request"""
    care_request = get_object_or_404(CareRequest, id=request_id)
    
    # Check permissions
    if request.user.role == 'family' and care_request.family != request.user:
        messages.error(request, 'You do not have permission to view this request.')
        return redirect('index')
    
    # Check if current user has already applied (for caretakers)
    has_applied = False
    if request.user.role == 'caretaker':
        has_applied = CareApplication.objects.filter(
            caretaker=request.user,
            request=care_request
        ).exists()
    
    # Get application counts
    from django.db.models import Count
    application_stats = CareApplication.objects.filter(request=care_request).aggregate(
        total=Count('id'),
        pending=Count('id', filter=Q(status='pending')),
        shortlisted=Count('id', filter=Q(status='shortlisted')),
        accepted=Count('id', filter=Q(status='accepted')),
        rejected=Count('id', filter=Q(status='rejected')),
    )
    
    context = {
        'request': care_request,
        'user': request.user,
        'has_applied': has_applied,
        'application_stats': application_stats,
    }
    return render(request, 'requests/request_detail.html', context)



# ----------------------------------------------------------------------------
# Edit a care request (for families)
# ----------------------------------------------------------------------------
@login_required
def edit_request(request, request_id):
    """Edit a care request (for families)"""
    if request.user.role != 'family':
        messages.error(request, '❌ Access denied.')
        return redirect('index')
    
    care_request = get_object_or_404(CareRequest, id=request_id, family=request.user)
    
    # Use the can_edit() method from the model
    if not care_request.can_edit():
        messages.error(request, f'❌ This request cannot be edited. Only drafts can be edited. Current status: {care_request.get_status_display()}')
        return redirect('request_detail', request_id=care_request.id)
    
    if request.method == 'POST':
        try:
            # Check action type
            action = request.POST.get('action', '')
            
            # Update fields from POST data - using correct field names
            care_request.patient_name = request.POST.get('patient_name', care_request.patient_name)
            
            patient_age = request.POST.get('patient_age')
            if patient_age:
                care_request.patient_age = int(patient_age)
            
            # Patient gender
            patient_gender = request.POST.get('patient_gender')
            if patient_gender:
                care_request.patient_gender = patient_gender
            
            # Medical condition field
            care_request.medical_condition = request.POST.get('medical_conditions', care_request.medical_condition)
            
            # Medical details
            care_request.mobility_status = request.POST.get('mobility_status', care_request.mobility_status)
            care_request.cognitive_status = request.POST.get('cognitive_status', care_request.cognitive_status)
            
            # Care type and urgency
            care_request.care_type = request.POST.get('care_type', care_request.care_type)
            care_request.urgency_level = request.POST.get('urgency_level', care_request.urgency_level)
            
            # Salary and payment
            salary = request.POST.get('salary_offered')
            if salary:
                care_request.salary_offered = float(salary)
            
            care_request.payment_frequency = request.POST.get('payment_frequency', care_request.payment_frequency)
            care_request.negotiable = request.POST.get('negotiable') == 'on'
            
            # Schedule
            start_date = request.POST.get('start_date')
            if start_date:
                from datetime import datetime
                care_request.start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            
            shift_timing = request.POST.get('shift_timing')
            if shift_timing:
                care_request.shift_timing = shift_timing
            
            duration = request.POST.get('duration_days')
            if duration:
                care_request.duration_days = int(duration)
            
            # Working hours
            hours_per_day = request.POST.get('hours_per_day')
            if hours_per_day:
                care_request.hours_per_day = float(hours_per_day)
            
            days_per_week = request.POST.get('days_per_week')
            if days_per_week:
                care_request.days_per_week = int(days_per_week)
            
            # Location
            care_request.address = request.POST.get('address', care_request.address)
            care_request.city = request.POST.get('city', care_request.city)
            care_request.state = request.POST.get('state', care_request.state)
            care_request.pincode = request.POST.get('pincode', care_request.pincode)
            care_request.landmark = request.POST.get('landmark', care_request.landmark)
            
            # Preferences
            care_request.gender_preference = request.POST.get('gender_preference', care_request.gender_preference)
            
            age_min = request.POST.get('age_preference_min')
            if age_min:
                care_request.age_preference_min = int(age_min)
            
            age_max = request.POST.get('age_preference_max')
            if age_max:
                care_request.age_preference_max = int(age_max)
            
            care_request.language_preference = request.POST.get('language_preference', care_request.language_preference)
            
            # Skills and qualifications
            care_request.required_skills = request.POST.get('required_skills', care_request.required_skills)
            care_request.preferred_qualifications = request.POST.get('preferred_qualifications', care_request.preferred_qualifications)
            
            # Additional requirements
            care_request.special_requirements = request.POST.get('special_requirements', care_request.special_requirements)
            care_request.equipment_provided = request.POST.get('equipment_provided', care_request.equipment_provided)
            
            # Accommodation
            care_request.accommodation_provided = request.POST.get('accommodation_provided') == 'on'
            care_request.accommodation_details = request.POST.get('accommodation_details', care_request.accommodation_details)
            
            # Interview
            care_request.interview_required = request.POST.get('interview_required') == 'on'
            care_request.interview_type = request.POST.get('interview_type', care_request.interview_type)
            
            # Emergency contact (new fields)
            care_request.emergency_contact_name = request.POST.get('emergency_contact_name', care_request.emergency_contact_name)
            care_request.emergency_contact_phone = request.POST.get('emergency_contact_phone', care_request.emergency_contact_phone)
            
            # Care details (new field)
            care_request.care_details = request.POST.get('care_details', care_request.care_details)
            
            # Handle action
            if action == 'publish' and care_request.status == 'draft':
                # Use the model's publish method
                care_request.publish()
                messages.success(request, '✅ Request published successfully! It is now visible to caregivers.')
                return redirect('request_detail', request_id=care_request.id)
                
            elif action == 'save_draft':
                care_request.status = 'draft'
                care_request.save()
                messages.success(request, '✅ Draft saved successfully!')
                return redirect('my_requests')
                
            else:
                care_request.save()
                messages.success(request, '✅ Request updated successfully!')
                return redirect('request_detail', request_id=care_request.id)
            
        except ValueError as e:
            messages.error(request, f'❌ Invalid data format: {str(e)}')
        except Exception as e:
            messages.error(request, f'❌ Error updating request: {str(e)}')
    
    # GET request - show edit form
    from apps.Applications.models import CareApplication
    
    applications_count = CareApplication.objects.filter(request=care_request).count()
    pending_count = CareApplication.objects.filter(request=care_request, status='pending').count()
    shortlisted_count = CareApplication.objects.filter(
        request=care_request, 
        status='shortlisted'
    ).count()
    offers_sent_count = CareApplication.objects.filter(
        request=care_request,
        status__in=['offer_sent', 'offer_accepted', 'offer_declined']
    ).count()
    
    # Check if request has any applications (to show warning)
    has_applications = applications_count > 0
    
    context = {
        'care_request': care_request,
        'applications_count': applications_count,
        'pending_count': pending_count,
        'shortlisted_count': shortlisted_count,
        'offers_sent_count': offers_sent_count,
        'has_applications': has_applications,
        'errors': {},
        'STATUS_CHOICES': CareRequest.STATUS_CHOICES,
        'CARE_TYPES': CareRequest.CARE_TYPES,
        'GENDER_PREFERENCES': CareRequest.GENDER_PREFERENCES,
        'PAYMENT_FREQUENCY': CareRequest.PAYMENT_FREQUENCY,
        'URGENCY_LEVELS': CareRequest.URGENCY_LEVELS,
    }
    return render(request, 'requests/edit_request.html', context)


# Close or reopen a care request (for families)
# ----------------------------------------------------------------------------
@login_required
def close_request(request, request_id):
    """Close or reopen a care request (for families)"""
    if request.user.role != 'family':
        messages.error(request, '❌ Access denied. Only family members can perform this action.')
        return redirect('index')
    
    # Get the care request and verify ownership
    care_request = get_object_or_404(CareRequest, id=request_id, family=request.user)
    
    if request.method == 'POST':
        try:
            if care_request.status == 'open':
                # Close the request
                care_request.status = 'closed'
                care_request.closed_at = timezone.now()
                
                # Reject all pending applications
                from apps.Applications.models import CareApplication
                CareApplication.objects.filter(
                    request=care_request,
                    status='pending'
                ).update(status='rejected', rejection_note='Request closed by family')
                
                care_request.save()
                messages.success(request, f'✅ Request for {care_request.patient_name} has been closed successfully.')
                
            elif care_request.status == 'closed':
                # Reopen the request (only if no assigned caretaker)
                if care_request.assigned_caretaker:
                    messages.error(request, '❌ Cannot reopen a request that has an assigned caretaker.')
                    return redirect('request_detail', request_id=care_request.id)
                
                care_request.status = 'open'
                care_request.closed_at = None
                care_request.save()
                messages.success(request, f'✅ Request for {care_request.patient_name} has been reopened successfully.')
                
            else:
                messages.error(request, f'❌ Cannot close a request with status: {care_request.get_status_display()}')
                return redirect('request_detail', request_id=care_request.id)
            
        except Exception as e:
            messages.error(request, f'❌ Error closing request: {str(e)}')
            
    return redirect('request_detail', request_id=care_request.id)



# ----------------------------------------------------------------------------
# Delete a care request (for families) - Only drafts can be deleted
# ----------------------------------------------------------------------------
@login_required
def delete_request(request, request_id):
    """Delete a care request (for families) - Only drafts can be deleted"""
    if request.user.role != 'family':
        messages.error(request, 'Access denied. Only family members can perform this action.')
        return redirect('index')
    
    # Get the care request and verify ownership
    care_request = get_object_or_404(CareRequest, id=request_id, family=request.user)
    
    if request.method == 'POST':
        # Only allow deletion of draft requests
        if care_request.status == 'draft':
            request_title = care_request.patient_name
            care_request.delete()
            messages.success(request, f'Request "{request_title}" has been deleted successfully.')
            return redirect('my_requests')
        else:
            messages.error(request, 'Only draft requests can be deleted. Published requests must be closed instead.')
            return redirect('request_detail', request_id=care_request.id)
    
    # GET request - show confirmation page
    return render(request, 'requests/delete_request_confirm.html', {
        'care_request': care_request
    })


# ----------------------------------------------------------------------------
# Save draft without publishing (for families)
# ----------------------------------------------------------------------------
@login_required
def save_draft(request, request_id):
    """Save draft without publishing (for families)"""
    if request.user.role != 'family':
        messages.error(request, '❌ Access denied.')
        return redirect('index')
    
    care_request = get_object_or_404(CareRequest, id=request_id, family=request.user)
    
    # Only allow saving if request is draft
    if not care_request.can_edit():
        messages.error(request, '❌ Only draft requests can be saved as draft.')
        return redirect('request_detail', request_id=care_request.id)
    
    if request.method == 'POST':
        try:
            # Update all fields with correct names
            care_request.patient_name = request.POST.get('patient_name', care_request.patient_name)
            
            patient_age = request.POST.get('patient_age')
            if patient_age:
                care_request.patient_age = int(patient_age)
            
            care_request.patient_gender = request.POST.get('patient_gender', care_request.patient_gender)
            care_request.medical_condition = request.POST.get('medical_conditions', care_request.medical_condition)
            care_request.care_type = request.POST.get('care_type', care_request.care_type)
            
            # Medical details
            care_request.mobility_status = request.POST.get('mobility_status', care_request.mobility_status)
            care_request.cognitive_status = request.POST.get('cognitive_status', care_request.cognitive_status)
            care_request.urgency_level = request.POST.get('urgency_level', care_request.urgency_level)
            
            # Schedule
            duration = request.POST.get('duration_days')
            if duration:
                care_request.duration_days = int(duration)
            
            start_date = request.POST.get('start_date')
            if start_date:
                from datetime import datetime
                care_request.start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            
            care_request.shift_timing = request.POST.get('shift_timing', care_request.shift_timing)
            
            # Working hours
            hours_per_day = request.POST.get('hours_per_day')
            if hours_per_day:
                care_request.hours_per_day = float(hours_per_day)
            
            days_per_week = request.POST.get('days_per_week')
            if days_per_week:
                care_request.days_per_week = int(days_per_week)
            
            # Location
            care_request.address = request.POST.get('address', care_request.address)
            care_request.city = request.POST.get('city', care_request.city)
            care_request.state = request.POST.get('state', care_request.state)
            care_request.pincode = request.POST.get('pincode', care_request.pincode)
            care_request.landmark = request.POST.get('landmark', care_request.landmark)
            
            # Compensation
            salary = request.POST.get('salary_offered')
            if salary:
                care_request.salary_offered = float(salary)
            
            care_request.payment_frequency = request.POST.get('payment_frequency', care_request.payment_frequency)
            care_request.negotiable = request.POST.get('negotiable') == 'on'
            
            # Preferences
            care_request.gender_preference = request.POST.get('gender_preference', care_request.gender_preference)
            
            age_min = request.POST.get('age_preference_min')
            if age_min:
                care_request.age_preference_min = int(age_min)
            
            age_max = request.POST.get('age_preference_max')
            if age_max:
                care_request.age_preference_max = int(age_max)
            
            care_request.language_preference = request.POST.get('language_preference', care_request.language_preference)
            
            # Skills
            care_request.required_skills = request.POST.get('required_skills', care_request.required_skills)
            care_request.preferred_qualifications = request.POST.get('preferred_qualifications', care_request.preferred_qualifications)
            
            # Additional requirements
            care_request.special_requirements = request.POST.get('special_requirements', care_request.special_requirements)
            care_request.equipment_provided = request.POST.get('equipment_provided', care_request.equipment_provided)
            
            # Accommodation
            care_request.accommodation_provided = request.POST.get('accommodation_provided') == 'on'
            care_request.accommodation_details = request.POST.get('accommodation_details', care_request.accommodation_details)
            
            # Interview
            care_request.interview_required = request.POST.get('interview_required') == 'on'
            care_request.interview_type = request.POST.get('interview_type', care_request.interview_type)
            
            # New fields
            care_request.emergency_contact_name = request.POST.get('emergency_contact_name', care_request.emergency_contact_name)
            care_request.emergency_contact_phone = request.POST.get('emergency_contact_phone', care_request.emergency_contact_phone)
            care_request.care_details = request.POST.get('care_details', care_request.care_details)
            
            care_request.status = 'draft'
            care_request.save()
            
            messages.success(request, '✅ Draft saved successfully! You can continue editing later.')
            
        except Exception as e:
            messages.error(request, f'❌ Error saving draft: {str(e)}')
        
        return redirect('my_requests')
    
    return redirect('request_detail', request_id=care_request.id)