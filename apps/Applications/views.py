from django.utils import timezone
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.core.paginator import Paginator
from apps.Applications.models import CareApplication
from apps.Requests.models import CareRequest
from apps.Users.models import User, CaretakerProfile


# ============================================================================
# CARETAKER VIEWS
# ============================================================================

# -------------------------------------------------------------------------
# Apply for a care request
# -------------------------------------------------------------------------
@login_required
def apply_request(request, request_id):
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

    if request.method == "POST":
        message = request.POST.get("message", "").strip()
        proposed_rate = request.POST.get("proposed_rate")

        if not message or not proposed_rate:
            messages.error(request, "All fields are required.")
            return render(request, "applications/apply_request.html", {
                "care_request": care_request
            })

        # Prevent duplicate application
        if CareApplication.objects.filter(
            request=care_request,
            caretaker=request.user
        ).exists():
            messages.error(request, "You have already applied for this request.")
            return redirect("my_applications")

        CareApplication.objects.create(
            request=care_request,
            caretaker=request.user,
            message=message,
            proposed_rate=proposed_rate,
            status="pending"
        )

        messages.success(request, "Application submitted successfully!")
        return redirect("my_applications")

    return render(request, "applications/apply_request.html", {
        "care_request": care_request
    })


# -------------------------------------------------------------------------
# View my applications (caretaker)
# -------------------------------------------------------------------------
@login_required
def my_applications(request):
    """View for caretakers to see their applications"""
    if request.user.role != 'caretaker':
        messages.error(request, 'Access denied.')
        return redirect('index')
    
    # Get filter from query params
    status_filter = request.GET.get('status', 'all')
    
    # Base queryset
    applications = CareApplication.objects.filter(
        caretaker=request.user
    ).select_related('request').order_by('-applied_at')
    
    # Apply status filter
    if status_filter != 'all':
        applications = applications.filter(status=status_filter)
    
    # Pagination
    paginator = Paginator(applications, 10)
    page = request.GET.get('page')
    applications_page = paginator.get_page(page)
    
    context = {
        'applications': applications_page,
        'status_filter': status_filter,
    }
    return render(request, 'applications/my_applications.html', context)


# -------------------------------------------------------------------------
# Withdraw application (caretaker)
# -------------------------------------------------------------------------
@login_required
def withdraw_application(request, application_id):
    """Withdraw an application"""
    if request.user.role != 'caretaker':
        messages.error(request, 'Access denied.')
        return redirect('index')
    
    application = get_object_or_404(
        CareApplication, 
        id=application_id, 
        caretaker=request.user,
        status='pending'  # Only allow withdrawing pending applications
    )
    
    if request.method == 'POST':
        application.status = 'withdrawn'
        application.save()
        messages.success(request, 'Application withdrawn successfully.')
        return redirect('my_applications')
    
    return render(request, 'applications/withdraw_confirm.html', {
        'application': application
    })


# -------------------------------------------------------------------------
# Respond to offer (caretaker)
# -------------------------------------------------------------------------
@login_required
def respond_to_offer(request, application_id, response):
    """Caretaker responds to an offer (accept/decline)"""
    if request.user.role != 'caretaker':
        messages.error(request, 'Access denied.')
        return redirect('index')
    
    application = get_object_or_404(
        CareApplication, 
        id=application_id,
        caretaker=request.user,
        status='offer_sent'
    )
    
    # Check if offer has expired
    if application.offer_expires_at and application.offer_expires_at < timezone.now():
        application.expire_offer()
        messages.error(request, 'This offer has expired.')
        return redirect('my_applications')
    
    if response == 'accept':
        with transaction.atomic():
            application.accept_offer()
            
            # TODO: Send notification to family
            # send_offer_accepted_notification(application)
            
            messages.success(request, 'Congratulations! You have accepted the offer. The family has been notified.')
    
    elif response == 'decline':
        application.decline_offer()
        
        # TODO: Send notification to family
        # send_offer_declined_notification(application)
        
        messages.info(request, 'You have declined the offer.')
    
    else:
        messages.error(request, 'Invalid response.')
    
    return redirect('my_applications')

# -------------------------------------------------------------------------
# 
# -------------------------------------------------------------------------
@login_required
def view_offer(request, application_id):
    """View full offer details (for caretakers)"""
    if request.user.role != 'caretaker':
        messages.error(request, 'Access denied.')
        return redirect('index')
    
    application = get_object_or_404(
        CareApplication, 
        id=application_id,
        caretaker=request.user,
        status='offer_sent'
    )
    
    context = {
        'application': application
    }
    return render(request, 'applications/view_offer.html', context)

# ============================================================================
# FAMILY VIEWS
# ============================================================================

# -------------------------------------------------------------------------
# Accept application (direct hire without shortlist)
# -------------------------------------------------------------------------
@login_required
def accept_application(request, application_id):
    """Accept an application and assign caretaker"""
    if request.user.role != 'family':
        messages.error(request, 'Access denied.')
        return redirect('index')
    
    application = get_object_or_404(
        CareApplication, 
        id=application_id,
        request__family=request.user
    )
    
    if application.status != 'pending':
        messages.error(request, 'Only pending applications can be accepted directly.')
        return redirect('request_applications', request_id=application.request.id)
    
    # Update application status
    application.status = 'accepted'
    application.save()
    
    # Update the care request with assigned caretaker
    care_request = application.request
    care_request.assigned_caretaker = application.caretaker
    care_request.assigned_date = timezone.now()
    care_request.status = 'assigned'
    care_request.save()
    
    # Reject all other applications for this request
    CareApplication.objects.filter(
        request=care_request
    ).exclude(
        id=application.id
    ).update(status='rejected')
    
    messages.success(request, f'Application accepted. {application.caretaker.get_full_name()} has been assigned.')
    return redirect('request_applications', request_id=care_request.id)


# -------------------------------------------------------------------------
# Reject application
# -------------------------------------------------------------------------
@login_required
def reject_application(request, application_id):
    """Reject an application"""
    if request.user.role != 'family':
        messages.error(request, 'Access denied.')
        return redirect('index')
    
    application = get_object_or_404(
        CareApplication, 
        id=application_id,
        request__family=request.user
    )
    
    if application.status in ['pending', 'shortlisted']:
        application.status = 'rejected'
        application.rejection_note = request.POST.get('rejection_note', '')
        application.save()
        messages.success(request, 'Application rejected.')
    else:
        messages.error(request, 'This application cannot be rejected.')
    
    return redirect('request_applications', request_id=application.request.id)


# -------------------------------------------------------------------------
# View applications for a request
# -------------------------------------------------------------------------
@login_required
def request_applications(request, request_id):
    """View applications for a specific care request (for families)"""
    if request.user.role != 'family':
        messages.error(request, 'Access denied. Only family members can view applications.')
        return redirect('index')
    
    care_request = get_object_or_404(CareRequest, id=request_id, family=request.user)
    status_filter = request.GET.get('status', 'all')
    
    applications = CareApplication.objects.filter(
        request=care_request
    ).select_related(
        'caretaker',
        'caretaker__caretaker_profile'
    ).order_by('-applied_at')
    
    if status_filter != 'all':
        applications = applications.filter(status=status_filter)
    
    context = {
        'care_request': care_request,
        'applications': applications,
        'status_filter': status_filter,
    }
    return render(request, 'applications/request_applications.html', context)


# -------------------------------------------------------------------------
# Shortlist application
# -------------------------------------------------------------------------
@login_required
def shortlist_application(request, application_id):
    """Shortlist an application"""
    if request.user.role != 'family':
        messages.error(request, 'Access denied.')
        return redirect('index')
    
    application = get_object_or_404(
        CareApplication, 
        id=application_id,
        request__family=request.user
    )
    
    if request.method == 'POST':
        notes = request.POST.get('notes', '')
        
        # Check if this is the first shortlisted candidate
        shortlisted_count = CareApplication.objects.filter(
            request=application.request,
            status='shortlisted'
        ).count()
        
        # Shortlist the application
        application.shortlist(notes=notes, rank=shortlisted_count + 1)
        
        # TODO: Send notification to caretaker
        # send_shortlist_notification(application)
        
        messages.success(request, f'{application.caretaker.get_full_name()} has been shortlisted.')
        return redirect('shortlisted_candidates', request_id=application.request.id)
    
    # GET request - show shortlist form
    return render(request, 'applications/shortlist_form.html', {
        'application': application
    })


# -------------------------------------------------------------------------
# View shortlisted candidates
# -------------------------------------------------------------------------
@login_required
def shortlisted_candidates(request, request_id):
    """View all shortlisted candidates for a request"""
    if request.user.role != 'family':
        messages.error(request, 'Access denied.')
        return redirect('index')
    
    care_request = get_object_or_404(CareRequest, id=request_id, family=request.user)
    
    shortlisted = CareApplication.objects.filter(
        request=care_request,
        status__in=['shortlisted', 'offer_sent']
    ).select_related(
        'caretaker',
        'caretaker__caretaker_profile'
    ).order_by('shortlist_rank', '-shortlisted_at')
    
    # Check for expired offers
    for app in shortlisted:
        if app.status == 'offer_sent' and app.is_offer_expired():
            app.expire_offer()
    
    # Refresh queryset after potential updates
    shortlisted = CareApplication.objects.filter(
        request=care_request,
        status__in=['shortlisted', 'offer_sent']
    ).select_related(
        'caretaker',
        'caretaker__caretaker_profile'
    ).order_by('shortlist_rank', '-shortlisted_at')
    
    context = {
        'care_request': care_request,
        'shortlisted_applications': shortlisted,
        'shortlisted_count': shortlisted.filter(status='shortlisted').count(),
        'offers_sent_count': shortlisted.filter(status='offer_sent').count(),
        'pending_decision_count': shortlisted.filter(
            status='offer_sent',
            offer_expires_at__gt=timezone.now()
        ).count(),
    }
    return render(request, 'applications/shortlisted_candidates.html', context)


# -------------------------------------------------------------------------
# Update shortlist rank
# -------------------------------------------------------------------------
@login_required
def update_shortlist_rank(request, application_id, direction):
    """Update the rank of a shortlisted candidate"""
    if request.user.role != 'family':
        messages.error(request, 'Access denied.')
        return redirect('index')
    
    application = get_object_or_404(
        CareApplication, 
        id=application_id,
        request__family=request.user,
        status='shortlisted'
    )
    
    # Get all shortlisted applications for this request
    shortlisted = CareApplication.objects.filter(
        request=application.request,
        status='shortlisted'
    ).order_by('shortlist_rank')
    
    current_rank = application.shortlist_rank
    
    if direction == 'up' and current_rank and current_rank > 1:
        # Swap with the one above
        above = shortlisted.filter(shortlist_rank=current_rank - 1).first()
        if above:
            above.shortlist_rank = current_rank
            above.save()
            application.shortlist_rank = current_rank - 1
            application.save()
            messages.success(request, 'Rank updated successfully.')
    
    elif direction == 'down' and current_rank and current_rank < shortlisted.count():
        # Swap with the one below
        below = shortlisted.filter(shortlist_rank=current_rank + 1).first()
        if below:
            below.shortlist_rank = current_rank
            below.save()
            application.shortlist_rank = current_rank + 1
            application.save()
            messages.success(request, 'Rank updated successfully.')
    
    return redirect('shortlisted_candidates', request_id=application.request.id)


# -------------------------------------------------------------------------
# Add shortlist notes
# -------------------------------------------------------------------------
@login_required
def add_shortlist_notes(request, application_id):
    """Add or edit notes for a shortlisted candidate"""
    if request.user.role != 'family':
        messages.error(request, 'Access denied.')
        return redirect('index')
    
    application = get_object_or_404(
        CareApplication, 
        id=application_id,
        request__family=request.user,
        status='shortlisted'
    )
    
    if request.method == 'POST':
        notes = request.POST.get('notes', '')
        application.shortlist_notes = notes
        application.save()
        messages.success(request, 'Notes saved successfully.')
        return redirect('shortlisted_candidates', request_id=application.request.id)
    
    return render(request, 'applications/shortlist_notes.html', {
        'application': application
    })


# -------------------------------------------------------------------------
# Remove from shortlist
# -------------------------------------------------------------------------
@login_required
def remove_shortlist(request, application_id):
    """Remove an application from shortlist"""
    if request.user.role != 'family':
        messages.error(request, 'Access denied.')
        return redirect('index')
    
    application = get_object_or_404(
        CareApplication, 
        id=application_id,
        request__family=request.user,
        status='shortlisted'
    )
    
    if request.method == 'POST':
        # Change status back to pending
        application.status = 'pending'
        application.shortlist_rank = None
        application.shortlist_notes = ''
        application.shortlisted_at = None
        application.save()
        
        # Reorder remaining shortlisted candidates
        remaining = CareApplication.objects.filter(
            request=application.request,
            status='shortlisted'
        ).order_by('shortlist_rank')
        
        for idx, app in enumerate(remaining, 1):
            app.shortlist_rank = idx
            app.save()
        
        messages.success(request, f'{application.caretaker.get_full_name()} removed from shortlist.')
        return redirect('shortlisted_candidates', request_id=application.request.id)
    
    return render(request, 'applications/remove_shortlist_confirm.html', {
        'application': application
    })


# -------------------------------------------------------------------------
# Send offer to shortlisted candidate
# -------------------------------------------------------------------------
@login_required
def send_offer(request, application_id):
    """Send an offer to a shortlisted candidate"""
    if request.user.role != 'family':
        messages.error(request, 'Access denied.')
        return redirect('index')
    
    application = get_object_or_404(
        CareApplication, 
        id=application_id,
        request__family=request.user,
        status='shortlisted'
    )
    
    if request.method == 'POST':
        # Collect offer details from form
        offer_details = {
            'start_date': request.POST.get('start_date'),
            'start_time': request.POST.get('start_time'),
            'reporting_address': request.POST.get('reporting_address'),
            'daily_duties': request.POST.get('daily_duties'),
            'special_instructions': request.POST.get('special_instructions'),
            'emergency_contact': request.POST.get('emergency_contact'),
            'emergency_phone': request.POST.get('emergency_phone'),
            'final_rate': request.POST.get('final_rate', application.proposed_rate),
            'payment_frequency': request.POST.get('payment_frequency', 'daily'),
            'accommodation_details': request.POST.get('accommodation_details', ''),
            'meals_provided': request.POST.get('meals_provided') == 'on',
            'offer_expiry_hours': int(request.POST.get('offer_expiry_hours', 48)),
        }
        
        # Send the offer
        application.send_offer(offer_details)
        
        # TODO: Send email notification
        # send_offer_email(application)
        
        messages.success(request, f'Offer sent to {application.caretaker.get_full_name()}. They have 48 hours to respond.')
        return redirect('shortlisted_candidates', request_id=application.request.id)
    
    # GET request - show offer form
    return render(request, 'applications/send_offer.html', {
        'application': application
    })


# ============================================================================
# SHARED VIEWS (Both roles)
# ============================================================================

# -------------------------------------------------------------------------
# Mark care as started
# -------------------------------------------------------------------------
@login_required
def mark_care_started(request, application_id):
    """Mark that care has started (can be done by either party)"""
    application = get_object_or_404(
        CareApplication, 
        id=application_id,
        status='accepted'
    )
    
    # Verify user is either the family or the caretaker for this application
    if request.user == application.request.family:
        application.mark_care_started('family')
        messages.success(request, 'Care marked as started. The caretaker will be notified.')
    
    elif request.user == application.caretaker:
        application.mark_care_started('caretaker')
        messages.success(request, 'You have marked care as started. The family will be notified.')
    
    else:
        messages.error(request, 'Access denied.')
        return redirect('index')
    
    return redirect('application_detail', application_id=application.id)


# -------------------------------------------------------------------------
# View caretaker profile (public)
# -------------------------------------------------------------------------
@login_required
def caretaker_profile_detail(request, user_id):
    """View caretaker profile details (for families)"""
    caretaker = get_object_or_404(User, id=user_id, role='caretaker')
    profile = get_object_or_404(CaretakerProfile, user=caretaker)

    context = {
        "caretaker": caretaker,
        "profile": profile
    }

    return render(request, "applications/caretaker_profile_detail.html", context)


# -------------------------------------------------------------------------
# Application detail view (for both roles)
# -------------------------------------------------------------------------
@login_required
def application_detail(request, application_id):
    """View details of a specific application"""
    application = get_object_or_404(
        CareApplication, 
        id=application_id
    )
    
    # Check permissions
    if request.user != application.caretaker and request.user != application.request.family:
        messages.error(request, 'Access denied.')
        return redirect('index')
    
    context = {
        'application': application
    }
    return render(request, 'applications/application_detail.html', context)