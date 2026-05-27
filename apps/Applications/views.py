from django.utils import timezone
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.core.paginator import Paginator
from apps.Applications.models import CareApplication
from apps.Requests.models import CareRequest
from apps.Users.models import User, CaretakerProfile
from apps.Notifications.models import Notification


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

        # Check for existing application
        existing_app = CareApplication.objects.filter(
            request=care_request, caretaker=request.user
        ).first()

        if existing_app:
            if existing_app.status == "withdrawn":
                # Reactivate withdrawn application
                existing_app.message = message
                existing_app.proposed_rate = proposed_rate
                existing_app.status = "pending"
                existing_app.applied_at = timezone.now()
                existing_app.save()
                application = existing_app
            else:
                messages.error(request, "You have already applied for this request.")
                return redirect("applications:my_applications")
        else:
            # Create the application
            application = CareApplication.objects.create(
                request=care_request,
                caretaker=request.user,
                message=message,
                proposed_rate=proposed_rate,
                status="pending",
            )

        # ========== CREATE NOTIFICATIONS ==========

        # 1. Notify the family who posted the request
        Notification.objects.create(
            recipient=care_request.family,
            sender=request.user,
            notification_type="application",
            title="New Application Received",
            message=f'{request.user.get_full_name() or request.user.username} has applied for your care request "{care_request.patient_name}".',
            icon="fa-file-alt",
            link=f"/applications/request/{care_request.id}/",
            is_read=False,
        )

        # 2. Notify the caretaker (confirmation)
        Notification.objects.create(
            recipient=request.user,
            notification_type="application",
            title="Application Submitted",
            message=f'Your application for "{care_request.patient_name}" has been submitted successfully.',
            icon="fa-check-circle",
            link="/applications/my-applications/",
            is_read=False,
        )

        messages.success(request, "Application submitted successfully!")
        return redirect("applications:my_applications")

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
        return redirect("applications:my_applications")

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
        return redirect("applications:my_applications")

    if response == "accept":
        with transaction.atomic():
            application.accept_offer()

            # ========== CREATE NOTIFICATION ==========
            Notification.objects.create(
                recipient=application.request.family,
                sender=request.user,
                notification_type="assignment",
                title="Offer Accepted",
                message=f"{application.caretaker.get_full_name()} has accepted your offer for {application.request.patient_name}.",
                icon="fa-check-circle",
                link=f"/applications/detail/{application.id}/",
                is_read=False,
            )

            messages.success(
                request,
                "Congratulations! You have accepted the offer. The family has been notified.",
            )

    elif response == "decline":
        if request.method == "POST":
            reason = request.POST.get("decline_reason", "").strip()
            application.decline_offer()
            
            # Save the decline reason
            if reason:
                application.offer_response_note = reason
                application.save(update_fields=['offer_response_note'])

            # ========== CREATE NOTIFICATION ==========
            Notification.objects.create(
                recipient=application.request.family,
                sender=request.user,
                notification_type="assignment",
                title="Offer Declined",
                message=f"{application.caretaker.get_full_name()} has declined your offer for {application.request.patient_name}.",
                icon="fa-times-circle",
                link=f"/applications/request/{application.request.id}/",
                is_read=False,
            )

            messages.info(request, "You have declined the offer.")
            return redirect("applications:my_applications")
        else:
            # Handle GET request: render the decline reason form
            return render(request, "applications/decline_offer.html", {"application": application})

    else:
        messages.error(request, "Invalid response.")

    return redirect("applications:my_applications")


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
        messages.error(
            request, "Access denied. Only family members can view applications."
        )
        return redirect("index")

    # Get all care requests posted by this family
    care_requests = CareRequest.objects.filter(family=request.user)

    # Get applications for these requests, excluding withdrawn ones
    applications = (
        CareApplication.objects.filter(request__in=care_requests)
        .exclude(status="withdrawn")
        .select_related("request", "caretaker", "caretaker__caretaker_profile")
        .order_by("-applied_at")
    )

    # Filter by status
    status = request.GET.get("status", "all")
    if status != "all":
        applications = applications.filter(status=status)

    # Count by status for the filter tabs
    total_count = applications.count()
    pending_count = applications.filter(status="pending").count()
    accepted_count = applications.filter(status="accepted").count()
    rejected_count = applications.filter(status="rejected").count()
    shortlisted_count = applications.filter(status="shortlisted").count()
    offer_sent_count = applications.filter(status="offer_sent").count()

    # Pagination
    paginator = Paginator(applications, 10)  # Show 10 applications per page
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    #  Get counts for sidebar
    received_count = applications.filter(
        status__in=["pending", "accepted", "rejected", "offer_sent"]
    ).count()
    sent_count = 0  # Will be implemented later for direct requests

    context = {
        "applications": page_obj,
        "total_count": total_count,
        "pending_count": pending_count,
        "accepted_count": accepted_count,
        "rejected_count": rejected_count,
        "shortlisted_count": shortlisted_count,
        "offer_sent_count": offer_sent_count,
        "current_status": status,
        "received_count": received_count,
        "sent_count": sent_count,
        "total_applications_count": total_count,
    }
    return render(request, "applications/family_applications.html", context)


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
        status="pending",
    )

    if request.method == "POST":
        # Update application status
        application.status = "accepted"
        application.accepted_at = timezone.now()
        application.save()

        # Update the care request
        care_request = application.request
        care_request.assigned_caretaker = application.caretaker
        care_request.assigned_date = timezone.now()
        care_request.status = "assigned"
        care_request.save()

        # Reject all other pending applications for this request
        CareApplication.objects.filter(request=care_request, status="pending").exclude(
            id=application.id
        ).update(
            status="rejected",
            rejection_note="Another candidate was selected",
            rejected_at=timezone.now(),
        )

        # ========== CREATE ASSIGNMENT ==========
        from apps.assignments.models import CareAssignment
        from decimal import Decimal

        # Create the assignment
        assignment = CareAssignment.objects.create(
            family=request.user,
            caretaker=application.caretaker,  # Direct caretaker object
            care_request=care_request,
            application=application,
            assigned_date=timezone.now(),
            start_date=timezone.now().date(),
            shift_type="full_time",  # Default shift type
            work_hours_per_day=8,  # Default hours
            hourly_rate=Decimal("200"),  # Default hourly rate
            monthly_salary=Decimal("48000"),  # 200 * 8 * 30
            notes="Auto-created from quick accept",
            status="active",
        )
        # ======================================

        messages.success(
            request,
            f"✅ Application from {application.caretaker.get_full_name()} has been accepted and assigned.",
        )
        return redirect("family_applications")

    return redirect("family_applications")


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
        status="pending",
    )

    if request.method == "POST":
        application.status = "rejected"
        application.rejection_note = request.POST.get(
            "rejection_note", "Rejected from dashboard"
        )
        application.rejected_at = timezone.now()
        application.save()

        messages.success(
            request,
            f"✅ Application from {application.caretaker.get_full_name()} has been rejected.",
        )
        return redirect("family_applications")

    return redirect("family_applications")


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
        return redirect(
            "applications:request_applications", request_id=application.request.id
        )

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

        # ========== CREATE ASSIGNMENT ==========
        from apps.assignments.models import CareAssignment
        from decimal import Decimal

        # Get hourly rate from application or use default
        hourly_rate = (
            Decimal(str(application.proposed_rate))
            if application.proposed_rate
            else Decimal("200")
        )
        work_hours = 8  # Default work hours per day
        monthly_salary = hourly_rate * work_hours * 30

        # Create the assignment
        assignment = CareAssignment.objects.create(
            family=request.user,
            caretaker=application.caretaker,
            care_request=care_request,
            application=application,
            assigned_date=timezone.now(),
            start_date=(
                care_request.start_date
                if care_request.start_date
                else timezone.now().date()
            ),
            shift_type="full_time",  # Default shift type
            work_hours_per_day=work_hours,
            hourly_rate=hourly_rate,
            monthly_salary=monthly_salary,
            notes=f"Created from direct acceptance of application #{application.id}",
            status="active",
        )
        # ======================================

        messages.success(
            request,
            f"✅ Application accepted. {application.caretaker.get_full_name()} has been assigned.",
        )

    return redirect("applications:request_applications", request_id=care_request.id)


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

        # ========== CREATE NOTIFICATION ==========
        Notification.objects.create(
            recipient=application.caretaker,
            sender=request.user,
            notification_type="application",
            title="Application Update",
            message=f'Your application for "{application.request.patient_name}" has been reviewed. Please check the status.',
            icon="fa-info-circle",
            link=f"/applications/detail/{application.id}/",
            is_read=False,
        )

        messages.success(request, "Application rejected.")
    else:
        messages.error(request, "This application cannot be rejected.")

    return redirect(
        "applications:request_applications", request_id=application.request.id
    )


# -------------------------------------------------------------------------
# View applications for a request
# -------------------------------------------------------------------------


@login_required
def request_applications(request, request_id):
    """View all applications for a specific request (for families)"""
    if request.user.role != "family":
        messages.error(request, "Access denied.")
        return redirect("index")

    care_request = get_object_or_404(CareRequest, id=request_id)

    if care_request.family != request.user:
        messages.error(
            request, "You do not have permission to view applications for this request."
        )
        return redirect("index")

    # Get applications, excluding withdrawn ones
    applications = (
        CareApplication.objects.filter(request=care_request)
        .exclude(status="withdrawn")
        .order_by("-applied_at")
    )

    # Add offer count for each application
    for app in applications:
        app.offer_count = app.offers.count() if hasattr(app, "offers") else 0

    from apps.assignments.models import CareAssignment
    is_position_filled = care_request.status == "assigned" or CareAssignment.objects.filter(care_request=care_request).exists()
    
    if is_position_filled and not care_request.assigned_caretaker:
        assignment = CareAssignment.objects.filter(care_request=care_request).first()
        if assignment:
            care_request.assigned_caretaker = assignment.caretaker

    context = {
        "care_request": care_request,
        "applications": applications,
        "is_position_filled": is_position_filled,
        "shortlisted_count": shortlisted_count,
        "has_active_shortlist": has_active_shortlist,
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

        # ========== CREATE NOTIFICATION ==========
        Notification.objects.create(
            recipient=application.caretaker,
            sender=request.user,
            notification_type="application",
            title="Application Shortlisted",
            message=f'Your application for "{application.request.patient_name}" has been shortlisted by the family.',
            icon="fa-star",
            link=f"/applications/detail/{application.id}/",
            is_read=False,
        )

        messages.success(
            request, f"{application.caretaker.get_full_name()} has been shortlisted."
        )
        return redirect(
            "applications:shortlisted_candidates", request_id=application.request.id
        )

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

    return redirect(
        "applications:shortlisted_candidates", request_id=application.request.id
    )


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
        return redirect(
            "applications:shortlisted_candidates", request_id=application.request.id
        )

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

        # ========== CREATE NOTIFICATION ==========
        Notification.objects.create(
            recipient=application.caretaker,
            sender=request.user,
            notification_type="application",
            title="Shortlist Update",
            message=f'Your application for "{application.request.patient_name}" has been removed from the shortlist.',
            icon="fa-info-circle",
            link=f"/applications/detail/{application.id}/",
            is_read=False,
        )

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
        return redirect(
            "applications:shortlisted_candidates", request_id=application.request.id
        )

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
    """Send an offer to a caretaker (for families)"""
    if request.user.role != "family":
        messages.error(request, "Access denied.")
        return redirect("users:index")

    application = get_object_or_404(CareApplication, id=application_id)
    
    # Get the care_request from the application (it's called 'request' in the model)
    care_request = application.request  # This is the CareRequest object
    
    # Check if the family owns this request
    if care_request.family != request.user:
        messages.error(request, "You do not have permission to send offers for this request.")
        return redirect("users:index")
    
    # Check if application can receive an offer
    can_offer, reason = application.can_receive_offer()
    if not can_offer:
        messages.error(request, f"❌ {reason}")
        return redirect("applications:request_applications", request_id=care_request.id)
    
    # Check if offer already sent
    if application.status == "offer_sent":
        messages.warning(request, "An offer has already been sent to this candidate.")
        return redirect("applications:application_detail", application_id=application.id)
    
    # Common context preparation (needed for both GET and POST error rendering)
    from datetime import date
    today = date.today()
    default_start_date = today
    if hasattr(care_request, 'start_date') and care_request.start_date:
        if care_request.start_date >= today:
            default_start_date = care_request.start_date
    
    default_shift_timing = "Day shift (9 AM - 5 PM)"
    if hasattr(care_request, 'preferred_shift') and care_request.preferred_shift:
        default_shift_timing = care_request.preferred_shift
    elif hasattr(care_request, 'shift_preference') and care_request.shift_preference:
        default_shift_timing = care_request.shift_preference
    elif hasattr(care_request, 'shift_timing') and care_request.shift_timing:
        default_shift_timing = care_request.shift_timing
    
    default_accommodation = "Not provided"
    if hasattr(care_request, 'accommodation_needed'):
        default_accommodation = "Accommodation needed" if care_request.accommodation_needed else "Accommodation not needed"
    elif hasattr(care_request, 'accommodation_details') and care_request.accommodation_details:
        default_accommodation = care_request.accommodation_details
    elif hasattr(care_request, 'accommodation_provided'):
        default_accommodation = "Provided" if care_request.accommodation_provided else "Not provided"
    
    default_payment_frequency = "daily"
    if hasattr(care_request, 'payment_frequency'):
        default_payment_frequency = care_request.payment_frequency
    
    from apps.Users.models import FamilyProfile
    family_profile = None
    try:
        family_profile = request.user.family_profile
    except:
        family_profile = FamilyProfile.objects.filter(user=request.user).first()
    
    profile_address_full = None
    if family_profile and family_profile.address:
        addr_parts = [family_profile.address]
        if family_profile.landmark: addr_parts.append(family_profile.landmark)
        if family_profile.city: addr_parts.append(family_profile.city)
        if family_profile.state: addr_parts.append(family_profile.state)
        if family_profile.pincode: addr_parts.append(family_profile.pincode)
        profile_address_full = ", ".join(addr_parts)
    
    cr_parts = [care_request.address]
    if hasattr(care_request, 'landmark') and care_request.landmark: cr_parts.append(care_request.landmark)
    if hasattr(care_request, 'city') and care_request.city: cr_parts.append(care_request.city)
    if hasattr(care_request, 'state') and care_request.state: cr_parts.append(care_request.state)
    if hasattr(care_request, 'pincode') and care_request.pincode: cr_parts.append(care_request.pincode)
    care_request_address_full = ", ".join(cr_parts)

    common_context = {
        "application": application,
        "care_request": care_request,
        "family_profile": family_profile,
        "profile_address_full": profile_address_full,
        "care_request_address_full": care_request_address_full,
        "default_start_date": default_start_date.strftime("%Y-%m-%d"),
        "default_shift_timing": default_shift_timing,
        "default_accommodation": default_accommodation,
        "default_payment_frequency": default_payment_frequency,
        "default_final_rate": care_request.salary_offered if hasattr(care_request, 'salary_offered') else None,
    }

    if request.method == "POST":
        # Extract form data
        start_date = request.POST.get("start_date")
        shift_timing = request.POST.get("shift_timing")
        reporting_address = request.POST.get("reporting_address")
        daily_duties = request.POST.get("daily_duties")
        special_instructions = request.POST.get("special_instructions")
        emergency_contact = request.POST.get("emergency_contact")
        emergency_phone = request.POST.get("emergency_phone")
        final_rate = request.POST.get("final_rate")
        payment_frequency = request.POST.get("payment_frequency")
        accommodation_details = request.POST.get("accommodation_details")
        meals_provided = request.POST.get("meals_provided") == "on"
        offer_expiry_hours = int(request.POST.get("offer_expiry_hours", 48))
        
        # Validate required fields
        if not all([start_date, reporting_address, daily_duties, final_rate]):
            messages.error(request, "Please fill in all required fields.")
            ctx = common_context.copy()
            ctx.update({
                "start_date": start_date,
                "shift_timing": shift_timing,
                "reporting_address": reporting_address,
                "daily_duties": daily_duties,
                "special_instructions": special_instructions,
                "emergency_contact": emergency_contact,
                "emergency_phone": emergency_phone,
                "final_rate": final_rate,
                "payment_frequency": payment_frequency,
                "accommodation_details": accommodation_details,
                "meals_provided": meals_provided,
                "offer_expiry_hours": offer_expiry_hours,
            })
            return render(request, "applications/send_offer.html", ctx)
        
        try:
            # Prepare offer details as a dictionary
            offer_details = {
                "start_date": start_date,
                "shift_timing": shift_timing,
                "reporting_address": reporting_address,
                "daily_duties": daily_duties,
                "special_instructions": special_instructions,
                "emergency_contact": emergency_contact,
                "emergency_phone": emergency_phone,
                "final_rate": final_rate,
                "payment_frequency": payment_frequency,
                "accommodation_details": accommodation_details,
                "meals_provided": meals_provided,
            }
            
            application.send_offer(offer_details, expiry_hours=offer_expiry_hours)
            
            from apps.Notifications.models import Notification
            Notification.objects.create(
                recipient=application.caretaker,
                sender=request.user,
                notification_type='offer',
                title='New Job Offer',
                message=f'You have received a job offer for "{care_request.patient_name}". Please respond within {offer_expiry_hours} hours.',
                icon='fa-envelope',
                link=f'/applications/offer/{application.id}/',
                is_read=False
            )
            
            # Consume any existing error messages before adding success message
            storage = messages.get_messages(request)
            for _ in storage:
                pass
                
            messages.success(request, f"Offer sent successfully to {application.caretaker.get_full_name()}!")
            return redirect("applications:shortlisted_candidates", request_id=care_request.id)
            
        except Exception as e:
            messages.error(request, f"Error sending offer: {str(e)}")
            ctx = common_context.copy()
            ctx.update({
                "start_date": start_date,
                "shift_timing": shift_timing,
                "reporting_address": reporting_address,
                "daily_duties": daily_duties,
                "special_instructions": special_instructions,
                "emergency_contact": emergency_contact,
                "emergency_phone": emergency_phone,
                "final_rate": final_rate,
                "payment_frequency": payment_frequency,
                "accommodation_details": accommodation_details,
                "meals_provided": meals_provided,
                "offer_expiry_hours": offer_expiry_hours,
            })
            return render(request, "applications/send_offer.html", ctx)
    
    # GET request
    return render(request, "applications/send_offer.html", common_context)




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

    # Try to get profile, but don't fail if it doesn't exist
    try:
        profile = CaretakerProfile.objects.get(user=caretaker)
    except CaretakerProfile.DoesNotExist:
        profile = None

    # Import CareApplication
    from .models import CareApplication

    # Total assignments (all approved applications)
    total_assignments = CareApplication.objects.filter(
        caretaker=caretaker, status="approved"
    ).count()

    # Completed jobs
    completed_jobs = CareApplication.objects.filter(
        caretaker=caretaker, status="completed"
    ).count()

    # In-progress assignments
    current_assignments = CareApplication.objects.filter(
        caretaker=caretaker, status="in_progress"
    ).count()

    # Pending applications
    pending_applications = CareApplication.objects.filter(
        caretaker=caretaker, status="pending"
    ).count()

    # Recent applications (last 5)
    recent_applications = CareApplication.objects.filter(caretaker=caretaker).order_by(
        "-applied_at"
    )[:5]

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
