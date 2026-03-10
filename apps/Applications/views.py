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

    care_request = get_object_or_404(CareRequest, id=request_id, status="open")

    if request.method == "POST":
        message = request.POST.get("message", "").strip()
        proposed_rate = request.POST.get("proposed_rate")

        if not message or not proposed_rate:
            messages.error(request, "All fields are required.")
            return render(
                request,
                "applications/apply_request.html",
                {"care_request": care_request},
            )

        # Prevent duplicate application
        if CareApplication.objects.filter(
            request=care_request, caretaker=request.user
        ).exists():
            messages.error(request, "You have already applied for this request.")
            return redirect("my_applications")

        CareApplication.objects.create(
            request=care_request,
            caretaker=request.user,
            message=message,
            proposed_rate=proposed_rate,
            status="pending",
        )

        messages.success(request, "Application submitted successfully!")
        return redirect("my_applications")

    return render(
        request, "applications/apply_request.html", {"care_request": care_request}
    )


# -------------------------------------------------------------------------
# View my applications (caretaker)
# -------------------------------------------------------------------------
@login_required
def my_applications(request):
    """View for caretakers to see their applications"""
    if request.user.role != "caretaker":
        messages.error(request, "Access denied.")
        return redirect("index")

    # Get filter from query params
    status_filter = request.GET.get("status", "all")

    # Base queryset
    applications = (
        CareApplication.objects.filter(caretaker=request.user)
        .select_related("request")
        .order_by("-applied_at")
    )

    # Apply status filter
    if status_filter != "all":
        applications = applications.filter(status=status_filter)

    # Pagination
    paginator = Paginator(applications, 10)
    page = request.GET.get("page")
    applications_page = paginator.get_page(page)

    context = {
        "applications": applications_page,
        "status_filter": status_filter,
    }
    return render(request, "applications/my_applications.html", context)


# -------------------------------------------------------------------------
# Withdraw application (caretaker)
# -------------------------------------------------------------------------


@login_required
def withdraw_application(request, application_id):
    application = get_object_or_404(
        CareApplication, id=application_id, caretaker=request.user
    )

    # DEBUG: Print all attributes of the application object
    print("\n" + "=" * 50)
    print("APPLICATION DEBUG:")
    print(f"Application ID: {application.id}")
    print(f"Available attributes:")
    for attr in dir(application):
        if not attr.startswith("_"):  # Skip private attributes
            try:
                value = getattr(application, attr)
                if not callable(value):  # Skip methods
                    print(f"  - {attr}: {value}")
            except:
                pass
    print("=" * 50 + "\n")

    if request.method == "POST":
        # Handle withdrawal
        if application.status in ["pending", "shortlisted"]:
            application.status = "withdrawn"
            application.save()
            messages.success(request, "Application withdrawn successfully.")
        else:
            messages.error(request, "This application cannot be withdrawn.")
        return redirect("my_applications")

    return render(
        request, "applications/withdraw_confirm.html", {"application": application}
    )


# -------------------------------------------------------------------------
# Respond to offer (caretaker)
# -------------------------------------------------------------------------
@login_required
def respond_to_offer(request, application_id, response):
    """Caretaker responds to an offer (accept/decline)"""
    if request.user.role != "caretaker":
        messages.error(request, "Access denied.")
        return redirect("index")

    application = get_object_or_404(
        CareApplication, id=application_id, caretaker=request.user, status="offer_sent"
    )

    # Check if offer has expired
    if application.offer_expires_at and application.offer_expires_at < timezone.now():
        application.expire_offer()
        messages.error(request, "This offer has expired.")
        return redirect("my_applications")

    if response == "accept":
        with transaction.atomic():
            application.accept_offer()

            # TODO: Send notification to family
            # send_offer_accepted_notification(application)

            messages.success(
                request,
                "Congratulations! You have accepted the offer. The family has been notified.",
            )

    elif response == "decline":
        application.decline_offer()

        # TODO: Send notification to family
        # send_offer_declined_notification(application)

        messages.info(request, "You have declined the offer.")

    else:
        messages.error(request, "Invalid response.")

    return redirect("my_applications")


# -------------------------------------------------------------------------
#
# -------------------------------------------------------------------------
@login_required
def view_offer(request, application_id):
    """View full offer details (for caretakers)"""
    if request.user.role != "caretaker":
        messages.error(request, "Access denied.")
        return redirect("index")

    application = get_object_or_404(
        CareApplication, id=application_id, caretaker=request.user, status="offer_sent"
    )

    context = {"application": application}
    return render(request, "applications/view_offer.html", context)


# ============================================================================
# FAMILY VIEWS
# ============================================================================

# -------------------------------------------------------------------------
# Family Applications Dashboard - View all applications across all requests
# -------------------------------------------------------------------------
@login_required
def family_applications(request):
    """View all applications received across all care requests (for families)"""
    if request.user.role != "family":
        messages.error(request, "Access denied. Only family members can view applications.")
        return redirect("index")

    # Get all care requests posted by this family
    care_requests = CareRequest.objects.filter(family=request.user)
    
    # Get applications for these requests
    applications = CareApplication.objects.filter(
        request__in=care_requests
    ).select_related(
        'request', 'caretaker', 'caretaker__caretaker_profile'
    ).order_by('-applied_at')

    # Filter by status
    status = request.GET.get('status', 'all')
    if status != 'all':
        applications = applications.filter(status=status)

    # Count by status for the filter tabs
    total_count = applications.count()
    pending_count = applications.filter(status='pending').count()
    accepted_count = applications.filter(status='accepted').count()
    rejected_count = applications.filter(status='rejected').count()
    shortlisted_count = applications.filter(status='shortlisted').count()
    offer_sent_count = applications.filter(status='offer_sent').count()

    # Pagination
    paginator = Paginator(applications, 10)  # Show 10 applications per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    #  Get counts for sidebar
    received_count = applications.filter(status__in=['pending', 'accepted', 'rejected', 'offer_sent']).count()
    sent_count = 0  # Will be implemented later for direct requests

    context = {
        'applications': page_obj,
        'total_count': total_count,
        'pending_count': pending_count,
        'accepted_count': accepted_count,
        'rejected_count': rejected_count,
        'shortlisted_count': shortlisted_count,
        'offer_sent_count': offer_sent_count,
        'current_status': status,
        'received_count': received_count,
        'sent_count': sent_count,
        'total_applications_count': total_count,
    }
    return render(request, 'applications/family_applications.html', context)


# -------------------------------------------------------------------------
# Family Applications - Quick accept from dashboard
# -------------------------------------------------------------------------
@login_required
def family_quick_accept(request, application_id):
    """Quick accept an application from the applications dashboard"""
    if request.user.role != "family":
        messages.error(request, "Access denied.")
        return redirect("index")

    application = get_object_or_404(
        CareApplication, 
        id=application_id, 
        request__family=request.user,
        status='pending'
    )

    if request.method == "POST":
        # Simple accept flow for dashboard
        application.status = 'accepted'
        application.accepted_at = timezone.now()
        application.save()

        # Update the care request
        care_request = application.request
        care_request.assigned_caretaker = application.caretaker
        care_request.assigned_date = timezone.now()
        care_request.status = 'assigned'
        care_request.save()

        # Reject all other pending applications for this request
        CareApplication.objects.filter(
            request=care_request,
            status='pending'
        ).exclude(id=application.id).update(
            status='rejected',
            rejection_note='Another candidate was selected',
            rejected_at=timezone.now()
        )

        messages.success(
            request, 
            f"✅ Application from {application.caretaker.get_full_name()} has been accepted and assigned."
        )
        return redirect('family_applications')

    return redirect('family_applications')


# -------------------------------------------------------------------------
# Family Applications - Quick reject from dashboard
# -------------------------------------------------------------------------
@login_required
def family_quick_reject(request, application_id):
    """Quick reject an application from the applications dashboard"""
    if request.user.role != "family":
        messages.error(request, "Access denied.")
        return redirect("index")

    application = get_object_or_404(
        CareApplication, 
        id=application_id, 
        request__family=request.user,
        status='pending'
    )

    if request.method == "POST":
        application.status = 'rejected'
        application.rejection_note = request.POST.get('rejection_note', 'Rejected from dashboard')
        application.rejected_at = timezone.now()
        application.save()

        messages.success(
            request, 
            f"✅ Application from {application.caretaker.get_full_name()} has been rejected."
        )
        return redirect('family_applications')

    return redirect('family_applications')





# -------------------------------------------------------------------------
# Accept application (direct hire without shortlist)
# -------------------------------------------------------------------------
@login_required
def accept_application(request, application_id):
    """
    DIRECT ACCEPT FLOW: Accept an application immediately
    If a shortlist exists for this post, freeze it and send offer automatically
    """
    if request.user.role != "family":
        messages.error(request, "Access denied.")
        return redirect("index")

    application = get_object_or_404(
        CareApplication, id=application_id, request__family=request.user
    )

    if application.status != "pending":
        messages.error(request, "Only pending applications can be accepted directly.")
        return redirect("request_applications", request_id=application.request.id)

    care_request = application.request

    # Check if there's an existing shortlist for this request
    existing_shortlist = CareApplication.objects.filter(
        request=care_request, status="shortlisted"
    ).exists()

    if existing_shortlist:
        # FREEZE THE SHORTLIST - Mark all shortlisted as frozen (not available)
        CareApplication.objects.filter(
            request=care_request, status="shortlisted"
        ).update(
            status="frozen",  # You need to add this status to your model
            frozen_at=timezone.now(),
            frozen_reason="Position filled through direct acceptance",
        )

        # Send offer automatically to the directly accepted applicant
        offer_details = {
            "start_date": (
                care_request.start_date.strftime("%Y-%m-%d")
                if care_request.start_date
                else None
            ),
            "start_time": (
                care_request.start_time.strftime("%H:%M")
                if care_request.start_time
                else "09:00"
            ),
            "reporting_address": care_request.address,
            "daily_duties": care_request.care_details,
            "special_instructions": "Direct acceptance - position filled immediately",
            "emergency_contact": request.user.phone,
            "emergency_phone": request.user.phone,
            "final_rate": application.proposed_rate,
            "payment_frequency": "daily",
            "offer_expiry_hours": 24,  # Shorter expiry for direct acceptance
        }

        # Send the offer
        application.send_offer(offer_details)

        messages.success(
            request,
            f"Application accepted directly. Shortlist has been frozen. "
            f"Offer letter sent to {application.caretaker.get_full_name()}.",
        )

    else:
        # No shortlist exists - simple direct assignment
        application.status = "accepted"
        application.accepted_at = timezone.now()
        application.save()

        # Update the care request with assigned caretaker
        care_request.assigned_caretaker = application.caretaker
        care_request.assigned_date = timezone.now()
        care_request.status = "assigned"
        care_request.save()

        # Reject all other applications
        CareApplication.objects.filter(request=care_request).exclude(
            id=application.id
        ).update(status="rejected")

        messages.success(
            request,
            f"Application accepted. {application.caretaker.get_full_name()} has been assigned.",
        )

    return redirect("request_applications", request_id=care_request.id)


# -------------------------------------------------------------------------
# Reject application
# -------------------------------------------------------------------------
@login_required
def reject_application(request, application_id):
    """Reject an application"""
    if request.user.role != "family":
        messages.error(request, "Access denied.")
        return redirect("index")

    application = get_object_or_404(
        CareApplication, id=application_id, request__family=request.user
    )

    if application.status in ["pending", "shortlisted"]:
        application.status = "rejected"
        application.rejection_note = request.POST.get("rejection_note", "")
        application.save()
        messages.success(request, "Application rejected.")
    else:
        messages.error(request, "This application cannot be rejected.")

    return redirect("request_applications", request_id=application.request.id)


# -------------------------------------------------------------------------
# View applications for a request
# -------------------------------------------------------------------------
@login_required
def request_applications(request, request_id):
    """View applications for a specific care request (for families)"""
    if request.user.role != "family":
        messages.error(
            request, "Access denied. Only family members can view applications."
        )
        return redirect("index")

    care_request = get_object_or_404(CareRequest, id=request_id, family=request.user)
    status_filter = request.GET.get("status", "all")

    applications = (
        CareApplication.objects.filter(request=care_request)
        .select_related("caretaker", "caretaker__caretaker_profile")
        .order_by("-applied_at")
    )

    if status_filter != "all":
        applications = applications.filter(status=status_filter)

    context = {
        "care_request": care_request,
        "applications": applications,
        "status_filter": status_filter,
    }
    return render(request, "applications/request_applications.html", context)


# -------------------------------------------------------------------------
# Shortlist application
# -------------------------------------------------------------------------
@login_required
def shortlist_application(request, application_id):
    """Shortlist an application"""
    if request.user.role != "family":
        messages.error(request, "Access denied.")
        return redirect("index")

    application = get_object_or_404(
        CareApplication, id=application_id, request__family=request.user
    )

    if request.method == "POST":
        notes = request.POST.get("notes", "")

        # Check if this is the first shortlisted candidate
        shortlisted_count = CareApplication.objects.filter(
            request=application.request, status="shortlisted"
        ).count()

        # Shortlist the application
        application.shortlist(notes=notes, rank=shortlisted_count + 1)

        # TODO: Send notification to caretaker
        # send_shortlist_notification(application)

        messages.success(
            request, f"{application.caretaker.get_full_name()} has been shortlisted."
        )
        return redirect("shortlisted_candidates", request_id=application.request.id)

    # GET request - show shortlist form
    return render(
        request, "applications/shortlist_form.html", {"application": application}
    )


# -------------------------------------------------------------------------
# View shortlisted candidates
# -------------------------------------------------------------------------
@login_required
def shortlisted_candidates(request, request_id):
    """View all shortlisted candidates for a request"""
    if request.user.role != "family":
        messages.error(request, "Access denied.")
        return redirect("index")

    care_request = get_object_or_404(CareRequest, id=request_id, family=request.user)

    shortlisted = (
        CareApplication.objects.filter(
            request=care_request, status__in=["shortlisted", "offer_sent"]
        )
        .select_related("caretaker", "caretaker__caretaker_profile")
        .order_by("shortlist_rank", "-shortlisted_at")
    )

    # Check for expired offers
    for app in shortlisted:
        if app.status == "offer_sent" and app.is_offer_expired():
            app.expire_offer()

    # Refresh queryset after potential updates
    shortlisted = (
        CareApplication.objects.filter(
            request=care_request, status__in=["shortlisted", "offer_sent"]
        )
        .select_related("caretaker", "caretaker__caretaker_profile")
        .order_by("shortlist_rank", "-shortlisted_at")
    )

    context = {
        "care_request": care_request,
        "shortlisted_applications": shortlisted,
        "shortlisted_count": shortlisted.filter(status="shortlisted").count(),
        "offers_sent_count": shortlisted.filter(status="offer_sent").count(),
        "pending_decision_count": shortlisted.filter(
            status="offer_sent", offer_expires_at__gt=timezone.now()
        ).count(),
    }
    return render(request, "applications/shortlisted_candidates.html", context)


# -------------------------------------------------------------------------
# Update shortlist rank
# -------------------------------------------------------------------------
@login_required
def update_shortlist_rank(request, application_id, direction):
    """Update the rank of a shortlisted candidate"""
    if request.user.role != "family":
        messages.error(request, "Access denied.")
        return redirect("index")

    application = get_object_or_404(
        CareApplication,
        id=application_id,
        request__family=request.user,
        status="shortlisted",
    )

    # Get all shortlisted applications for this request
    shortlisted = CareApplication.objects.filter(
        request=application.request, status="shortlisted"
    ).order_by("shortlist_rank")

    current_rank = application.shortlist_rank

    if direction == "up" and current_rank and current_rank > 1:
        # Swap with the one above
        above = shortlisted.filter(shortlist_rank=current_rank - 1).first()
        if above:
            above.shortlist_rank = current_rank
            above.save()
            application.shortlist_rank = current_rank - 1
            application.save()
            messages.success(request, "Rank updated successfully.")

    elif direction == "down" and current_rank and current_rank < shortlisted.count():
        # Swap with the one below
        below = shortlisted.filter(shortlist_rank=current_rank + 1).first()
        if below:
            below.shortlist_rank = current_rank
            below.save()
            application.shortlist_rank = current_rank + 1
            application.save()
            messages.success(request, "Rank updated successfully.")

    return redirect("shortlisted_candidates", request_id=application.request.id)


# -------------------------------------------------------------------------
# Add shortlist notes
# -------------------------------------------------------------------------
@login_required
def add_shortlist_notes(request, application_id):
    """Add or edit notes for a shortlisted candidate"""
    if request.user.role != "family":
        messages.error(request, "Access denied.")
        return redirect("index")

    application = get_object_or_404(
        CareApplication,
        id=application_id,
        request__family=request.user,
        status="shortlisted",
    )

    if request.method == "POST":
        notes = request.POST.get("notes", "")
        application.shortlist_notes = notes
        application.save()
        messages.success(request, "Notes saved successfully.")
        return redirect("shortlisted_candidates", request_id=application.request.id)

    return render(
        request, "applications/shortlist_notes.html", {"application": application}
    )


# -------------------------------------------------------------------------
# Remove from shortlist
# -------------------------------------------------------------------------
@login_required
def remove_shortlist(request, application_id):
    """Remove an application from shortlist"""
    if request.user.role != "family":
        messages.error(request, "Access denied.")
        return redirect("index")

    application = get_object_or_404(
        CareApplication,
        id=application_id,
        request__family=request.user,
        status="shortlisted",
    )

    if request.method == "POST":
        # Change status back to pending
        application.status = "pending"
        application.shortlist_rank = None
        application.shortlist_notes = ""
        application.shortlisted_at = None
        application.save()

        # Reorder remaining shortlisted candidates
        remaining = CareApplication.objects.filter(
            request=application.request, status="shortlisted"
        ).order_by("shortlist_rank")

        for idx, app in enumerate(remaining, 1):
            app.shortlist_rank = idx
            app.save()

        messages.success(
            request, f"{application.caretaker.get_full_name()} removed from shortlist."
        )
        return redirect("shortlisted_candidates", request_id=application.request.id)

    return render(
        request,
        "applications/remove_shortlist_confirm.html",
        {"application": application},
    )


# -------------------------------------------------------------------------
# Send offer to shortlisted candidate
# -------------------------------------------------------------------------

@login_required
def send_offer(request, application_id):
    """Send an offer letter to a caretaker"""
    # Get the application or return 404
    application = get_object_or_404(CareApplication, id=application_id)
    
    # Check if user is the family who owns the request
    if request.user != application.request.family:
        messages.error(request, "❌ Access denied. You don't have permission to send offers for this request.")
        return redirect('index')
    
    # Check if request is still open
    if application.request.status != 'open':
        messages.error(request, "❌ This request is no longer accepting applications.")
        return redirect('request_applications', request_id=application.request.id)
    
    # Check if application is in valid state for sending offer
    if application.status not in ['pending', 'shortlisted']:
        messages.error(request, f"❌ Cannot send offer to application with status: {application.get_status_display()}")
        return redirect('request_applications', request_id=application.request.id)
    
    if request.method == 'POST':
        try:
            # Get form data
            offer_message = request.POST.get('offer_message')
            proposed_rate = request.POST.get('proposed_rate')
            start_date = request.POST.get('start_date')
            offer_valid_until = request.POST.get('offer_valid_until')
            working_hours = request.POST.get('working_hours')
            special_terms = request.POST.get('special_terms', '')
            
            # Validate required fields
            if not all([offer_message, proposed_rate, start_date, offer_valid_until]):
                messages.error(request, "❌ Please fill in all required fields.")
                return redirect('request_applications', request_id=application.request.id)
            
            # Update application with offer details
            application.status = 'offer_sent'
            application.offer_message = offer_message
            application.offer_proposed_rate = proposed_rate
            application.offer_start_date = start_date
            application.offer_valid_until = offer_valid_until
            application.offer_working_hours = working_hours
            application.offer_special_terms = special_terms
            application.offer_sent_at = timezone.now()
            application.save()
            
            # Reject all other pending applications for this request
            # REMOVED the duplicate import - CareApplication is already imported at the top
            CareApplication.objects.filter(
                request=application.request,
                status='pending'
            ).exclude(id=application.id).update(
                status='rejected',
                rejection_note='Another candidate was selected',
                rejected_at=timezone.now()
            )
            
            # Freeze shortlisted applications
            CareApplication.objects.filter(
                request=application.request,
                status='shortlisted'
            ).exclude(id=application.id).update(
                status='frozen',
                frozen_reason='Offer sent to another candidate',
                frozen_at=timezone.now()
            )
            
            # Send email notification if checked
            if request.POST.get('notify_by_email'):
                # Add email sending logic here
                # You can implement this later
                pass
            
            messages.success(
                request, 
                f"✅ Offer letter sent successfully to {application.caretaker.get_full_name()}!"
            )
            
        except Exception as e:
            messages.error(request, f"❌ Error sending offer: {str(e)}")
        
        return redirect('request_applications', request_id=application.request.id)
    
    # If not POST, redirect to applications page
    return redirect('request_applications', request_id=application.request.id)

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
        CareApplication, id=application_id, status="accepted"
    )

    # Verify user is either the family or the caretaker for this application
    if request.user == application.request.family:
        application.mark_care_started("family")
        messages.success(
            request, "Care marked as started. The caretaker will be notified."
        )

    elif request.user == application.caretaker:
        application.mark_care_started("caretaker")
        messages.success(
            request, "You have marked care as started. The family will be notified."
        )

    else:
        messages.error(request, "Access denied.")
        return redirect("index")

    return redirect("application_detail", application_id=application.id)


# -------------------------------------------------------------------------
# View caretaker profile (public)
# -------------------------------------------------------------------------
@login_required
def caretaker_profile_detail(request, user_id):
    """View caretaker profile details (for families)"""
    caretaker = get_object_or_404(User, id=user_id, role="caretaker")
    profile = get_object_or_404(CaretakerProfile, user=caretaker)
    
    # Import CareApplication instead of Application
    from .models import CareApplication
    
    # Total assignments (all approved applications)
    total_assignments = CareApplication.objects.filter(
        caretaker=caretaker,  # Note: CareApplication uses caretaker as User, not CaretakerProfile
        status='approved'
    ).count()
    
    # Completed jobs
    completed_jobs = CareApplication.objects.filter(
        caretaker=caretaker,
        status='completed'
    ).count()
    
    # In-progress assignments
    current_assignments = CareApplication.objects.filter(
        caretaker=caretaker,
        status='in_progress'
    ).count()
    
    # Pending applications
    pending_applications = CareApplication.objects.filter(
        caretaker=caretaker,
        status='pending'
    ).count()
    
    # Recent applications (last 5)
    recent_applications = CareApplication.objects.filter(
        caretaker=caretaker
    ).order_by('-applied_at')[:5]

    context = {
        "caretaker": caretaker, 
        "profile": profile,
        "total_assignments": total_assignments,
        "completed_jobs": completed_jobs,
        "current_assignments": current_assignments,
        "pending_applications": pending_applications,
        "recent_applications": recent_applications,
    }

    return render(request, "applications/caretaker_profile_detail.html", context)


# -------------------------------------------------------------------------
# Application detail view (for both roles)
# -------------------------------------------------------------------------
@login_required
def application_detail(request, application_id):
    """View details of a specific application"""
    application = get_object_or_404(CareApplication, id=application_id)

    # Check permissions
    if (
        request.user != application.caretaker
        and request.user != application.request.family
    ):
        messages.error(request, "Access denied.")
        return redirect("index")

    context = {"application": application}
    return render(request, "applications/application_detail.html", context)
