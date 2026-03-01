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
    
    context = {
        "requests": requests,
        "applied_request_ids": applied_request_ids
    }
    return render(request, "requests/browse_requests.html", context)


# ----------------------------------------------------------------------------
# Apply for a request (for caretakers)
# ----------------------------------------------------------------------------
@login_required
def apply_for_request(request, request_id):
    """Apply for a care request (for caretakers)"""
    if request.user.role != "caretaker":
        messages.error(request, "Access denied.")
        return redirect("index")

    if not request.user.is_verified:
        return redirect("verification_pending")

    care_request = get_object_or_404(
        CareRequest,
        id=request_id,
        status="open"
    )

    # Check if already applied
    if CareApplication.objects.filter(
        request=care_request,
        caretaker=request.user
    ).exists():
        messages.warning(request, "You have already applied for this request.")
        return redirect("request_detail", request_id=care_request.id)

    if request.method == "POST":
        message = request.POST.get("message", "").strip()
        proposed_rate = request.POST.get("proposed_rate")

        if not message or not proposed_rate:
            messages.error(request, "All fields are required.")
            return render(request, "requests/apply_for_request.html", {
                "care_request": care_request
            })

        CareApplication.objects.create(
            request=care_request,
            caretaker=request.user,
            message=message,
            proposed_rate=proposed_rate,
            status="pending"
        )

        messages.success(request, "Application submitted successfully!")
        return redirect("my_applications")

    return render(request, "requests/apply_for_request.html", {
        "care_request": care_request
    })


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
    if status:
        requests_list = requests_list.filter(status=status)
    
    # Search
    search = request.GET.get('search')
    if search:
        requests_list = requests_list.filter(
            Q(patient_name__icontains=search) |
            Q(medical_condition__icontains=search)
        )
    
    context = {
        'requests': requests_list.order_by('-created_at')
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
    
    context = {
        'request': care_request,
        'user': request.user,
        'has_applied': has_applied,
    }
    return render(request, 'requests/request_detail.html', context)


# ----------------------------------------------------------------------------
# Edit a care request (for families)
# ----------------------------------------------------------------------------
@login_required
def edit_request(request, request_id):
    """Edit a care request (for families)"""
    if request.user.role != 'family':
        messages.error(request, 'Access denied.')
        return redirect('index')
    
    care_request = get_object_or_404(CareRequest, id=request_id, family=request.user)
    
    # Only allow editing if request is open or draft
    if care_request.status not in ['open', 'draft']:
        messages.error(request, 'This request cannot be edited.')
        return redirect('my_requests')
    
    if request.method == 'POST':
        # Update fields
        care_request.patient_name = request.POST.get('patient_name')
        care_request.patient_age = request.POST.get('patient_age')
        care_request.medical_condition = request.POST.get('medical_condition')
        care_request.care_type = request.POST.get('care_type')
        care_request.salary_offered = request.POST.get('salary_offered')
        care_request.shift_timing = request.POST.get('shift_timing')
        care_request.gender_preference = request.POST.get('gender_preference', 'any')
        care_request.special_requirements = request.POST.get('special_requirements')
        care_request.address = request.POST.get('address')
        care_request.start_date = request.POST.get('start_date')
        care_request.duration_days = request.POST.get('duration_days')
        care_request.save()
        
        messages.success(request, 'Request updated successfully!')
        return redirect('request_detail', request_id=care_request.id)
    
    context = {
        'request': care_request
    }
    return render(request, 'requests/edit_request.html', context)


# ----------------------------------------------------------------------------
# Close a care request (for families)
# ----------------------------------------------------------------------------
@login_required
def close_request(request, request_id):
    """Close a care request (for families)"""
    if request.user.role != 'family':
        messages.error(request, 'Access denied.')
        return redirect('index')
    
    care_request = get_object_or_404(CareRequest, id=request_id, family=request.user)
    
    if care_request.status == 'open':
        care_request.status = 'closed'
        care_request.save()
        messages.success(request, 'Request closed successfully.')
    else:
        messages.error(request, 'This request cannot be closed.')
    
    return redirect('my_requests')


# ----------------------------------------------------------------------------
# Delete a care request (for families)
# ----------------------------------------------------------------------------
@login_required
def delete_request(request, request_id):
    """Delete a care request (for families)"""
    if request.user.role != 'family':
        messages.error(request, 'Access denied.')
        return redirect('index')
    
    care_request = get_object_or_404(CareRequest, id=request_id, family=request.user)
    
    # Only allow deletion if request is open or draft
    if care_request.status in ['open', 'draft']:
        care_request.delete()
        messages.success(request, 'Request deleted successfully.')
    else:
        messages.error(request, 'Only open or draft requests can be deleted.')
    
    return redirect('my_requests')