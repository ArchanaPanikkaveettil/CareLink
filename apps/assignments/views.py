from django.shortcuts import render

# Create your views here.
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models import Q, Sum, Count, Avg
from django.core.paginator import Paginator
from django.http import JsonResponse
from datetime import datetime, timedelta, date
from decimal import Decimal

from .models import (
    CareAssignment,
    DailyCareReport,
    CareTask,
    CareNote,
    Attendance,
    SalaryPayment,
)
from apps.Users.models import User
from apps.Requests.models import CareRequest
from apps.Applications.models import CareApplication
from apps.Notifications.models import Notification


# ============================================================================
# ASSIGNMENT MANAGEMENT
# ============================================================================


@login_required
def my_caregivers(request):
    """Display all active caregivers assigned to the family"""
    if request.user.role != "family":
        messages.error(
            request, "Access denied. Only families can view their caregivers."
        )
        return redirect("users:index")

    # Get all active assignments for this family
    active_assignments = (
        CareAssignment.objects.filter(family=request.user, status="active")
        .select_related("caretaker", "care_request")
        .prefetch_related("attendance_records", "tasks", "care_notes", "daily_reports")
    )

    today = date.today()
    pending_tasks_total = 0
    unread_messages_total = 0
    unread_reports_total = 0

    for assignment in active_assignments:
        # Get caregiver's full name
        assignment.caregiver_name = (
            assignment.caretaker.get_full_name() or assignment.caretaker.username
        )

        # Today's attendance
        assignment.today_attendance = assignment.attendance_records.filter(
            date=today
        ).first()

        # Count pending tasks
        assignment.pending_tasks_count = assignment.tasks.filter(
            status__in=["pending", "in_progress"]
        ).count()
        pending_tasks_total += assignment.pending_tasks_count

        # Count unread notes (for family)
        assignment.unread_notes_count = assignment.care_notes.filter(
            read_by_family=False
        ).count()
        unread_messages_total += assignment.unread_notes_count

        # Count unread reports
        assignment.unread_reports_count = assignment.daily_reports.filter(
            family_read=False
        ).count()
        unread_reports_total += assignment.unread_reports_count

        # Calculate monthly salary correctly
        if assignment.monthly_salary:
            assignment.display_salary = assignment.monthly_salary
        else:
            # Calculate monthly salary: hourly_rate * work_hours_per_day * 30
            assignment.display_salary = (
                assignment.hourly_rate * assignment.work_hours_per_day * 30
            )

        # Format salary with commas
        assignment.formatted_salary = f"₹{assignment.display_salary:,.2f}"

    context = {
        "active_assignments": active_assignments,
        "total_caregivers": active_assignments.count(),
        "today": today,
        "pending_tasks_total": pending_tasks_total,
        "unread_messages_total": unread_messages_total,
        "unread_reports_total": unread_reports_total,
    }
    return render(request, "assignments/my_caregivers.html", context)


import json
from django.http import JsonResponse, HttpResponse


@login_required
def debug_caregivers(request):
    """Debug view to check what's in the database"""
    if request.user.role != "family":
        return JsonResponse({"error": "Access denied"}, status=403)

    from django.contrib.auth.models import User
    from apps.Applications.models import CareApplication
    from apps.Requests.models import CareRequest

    debug_info = {
        "current_user": {
            "id": request.user.id,
            "username": request.user.username,
            "role": request.user.role,
            "is_authenticated": request.user.is_authenticated,
        },
        "care_assignments": {
            "all": [],
            "active": [],
            "count": CareAssignment.objects.filter(family=request.user).count(),
        },
        "care_applications": {
            "accepted": [],
            "pending": [],
            "total": CareApplication.objects.filter(
                request__family=request.user
            ).count(),
        },
        "care_requests": {
            "total": CareRequest.objects.filter(family=request.user).count()
        },
    }

    # Get all assignments
    all_assignments = CareAssignment.objects.filter(family=request.user)
    for assignment in all_assignments:
        debug_info["care_assignments"]["all"].append(
            {
                "id": assignment.id,
                "caretaker": assignment.caretaker.username,
                "status": assignment.status,
                "assigned_date": str(assignment.assigned_date),
            }
        )

    # Get active assignments
    active = all_assignments.filter(status="active")
    for assignment in active:
        debug_info["care_assignments"]["active"].append(
            {"id": assignment.id, "caretaker": assignment.caretaker.username}
        )

    # Get accepted applications
    accepted_apps = CareApplication.objects.filter(
        request__family=request.user, status="accepted"
    )
    for app in accepted_apps:
        debug_info["care_applications"]["accepted"].append(
            {
                "id": app.id,
                "caretaker": (
                    app.caretaker.user.username
                    if hasattr(app.caretaker, "user")
                    else str(app.caretaker)
                ),
                "status": app.status,
            }
        )

    # Get pending applications
    pending_apps = CareApplication.objects.filter(
        request__family=request.user, status="pending"
    )
    for app in pending_apps:
        debug_info["care_applications"]["pending"].append(
            {
                "id": app.id,
                "caretaker": (
                    app.caretaker.user.username
                    if hasattr(app.caretaker, "user")
                    else str(app.caretaker)
                ),
            }
        )

    # Return formatted JSON
    return HttpResponse(
        json.dumps(debug_info, indent=2), content_type="application/json"
    )


@login_required
def create_assignment(request, application_id):
    """Create a care assignment from an accepted application"""
    if request.user.role != "family":
        messages.error(request, "Access denied. Only families can create assignments.")
        return redirect("users:index")

    application = get_object_or_404(
        CareApplication, id=application_id, status="accepted"
    )

    # Check if assignment already exists
    existing = CareAssignment.objects.filter(application=application).first()
    if existing:
        messages.info(request, "An assignment already exists for this application.")
        return redirect(
            "assignments:family_assignment_detail", assignment_id=existing.id
        )

    if request.method == "POST":
        try:
            # Calculate monthly salary if hourly rate provided
            hourly_rate = Decimal(request.POST.get("hourly_rate", 0))
            work_hours = Decimal(request.POST.get("work_hours_per_day", 8))
            monthly_salary = hourly_rate * work_hours * 30

            assignment = CareAssignment.objects.create(
                family=request.user,
                caretaker=application.caretaker.user,
                care_request=application.request,
                application=application,
                assigned_date=timezone.now(),
                start_date=request.POST.get("start_date"),
                shift_type=request.POST.get("shift_type", "full_time"),
                work_hours_per_day=work_hours,
                hourly_rate=hourly_rate,
                monthly_salary=monthly_salary if hourly_rate > 0 else None,
                notes=request.POST.get("notes", ""),
                status="active",
            )

            messages.success(
                request,
                f"Assignment created successfully! {application.caretaker.user.get_full_name()} is now assigned to you.",
            )
            return redirect(
                "assignments:family_assignment_detail", assignment_id=assignment.id
            )

        except Exception as e:
            messages.error(request, f"Error creating assignment: {str(e)}")

    context = {
        "application": application,
        "shift_choices": CareAssignment.SHIFT_CHOICES,
    }
    return render(request, "assignments/create_assignment.html", context)


@login_required
def family_assignments(request):
    """List all assignments for a family"""
    if request.user.role != "family":
        messages.error(request, "Access denied.")
        return redirect("users:index")

    assignments = (
        CareAssignment.objects.filter(family=request.user)
        .select_related("caretaker")
        .prefetch_related("attendance_records")
    )

    # Filter by status
    status_filter = request.GET.get("status", "")
    if status_filter:
        assignments = assignments.filter(status=status_filter)

    # Search
    search_query = request.GET.get("q", "")
    if search_query:
        assignments = assignments.filter(
            Q(caretaker__first_name__icontains=search_query)
            | Q(caretaker__last_name__icontains=search_query)
            | Q(caretaker__email__icontains=search_query)
        )

    # Pagination
    paginator = Paginator(assignments, 10)
    page = request.GET.get("page", 1)
    assignments = paginator.get_page(page)

    # Add summary for each assignment
    today = date.today()
    for assignment in assignments:
        # Process patient name for family list
        patient_name = assignment.care_request.elder_profile.name if (assignment.care_request.elder_profile and assignment.care_request.elder_profile.name) else assignment.care_request.patient_name
        
        display_patient_name = patient_name
        if patient_name:
            if " & " in patient_name:
                parts = patient_name.split(" & ")
                first_person = parts[0].strip()
                last_person = parts[-1].strip()
                if " " not in first_person and " " in last_person:
                    last_name = last_person.split(" ")[-1]
                    display_patient_name = f"{first_person} {last_name}"
                else:
                    display_patient_name = first_person
            elif " and " in patient_name:
                parts = patient_name.split(" and ")
                first_person = parts[0].strip()
                last_person = parts[-1].strip()
                if " " not in first_person and " " in last_person:
                    last_name = last_person.split(" ")[-1]
                    display_patient_name = f"{first_person} {last_name}"
                else:
                    display_patient_name = first_person
        
        assignment.display_patient_name = display_patient_name

        assignment.today_attendance = assignment.attendance_records.filter(
            date=today
        ).first()
        assignment.pending_tasks_count = assignment.tasks.filter(
            status__in=["pending", "in_progress"]
        ).count()
        assignment.unread_notes_count = assignment.care_notes.filter(
            read_by_family=False
        ).count()
        assignment.unread_reports_count = assignment.daily_reports.filter(
            family_read=False
        ).count()

    context = {
        "assignments": assignments,
        "status_filter": status_filter,
        "search_query": search_query,
    }
    return render(request, "assignments/family_assignments.html", context)


@login_required
def caretaker_assignments(request):
    """List all assignments for a caretaker"""
    if request.user.role != "caretaker":
        messages.error(request, "Access denied.")
        return redirect("users:index")

    assignments = CareAssignment.objects.filter(caretaker=request.user).select_related(
        "family", "care_request", "care_request__elder_profile"
    )

    # Add today's status
    today = date.today()
    for assignment in assignments:
        # Process patient name for caretaker list
        patient_name = assignment.care_request.elder_profile.name if (assignment.care_request.elder_profile and assignment.care_request.elder_profile.name) else assignment.care_request.patient_name
        
        display_patient_name = patient_name
        if patient_name:
            if " & " in patient_name:
                parts = patient_name.split(" & ")
                first_person = parts[0].strip()
                last_person = parts[-1].strip()
                if " " not in first_person and " " in last_person:
                    last_name = last_person.split(" ")[-1]
                    display_patient_name = f"{first_person} {last_name}"
                else:
                    display_patient_name = first_person
            elif " and " in patient_name:
                parts = patient_name.split(" and ")
                first_person = parts[0].strip()
                last_person = parts[-1].strip()
                if " " not in first_person and " " in last_person:
                    last_name = last_person.split(" ")[-1]
                    display_patient_name = f"{first_person} {last_name}"
                else:
                    display_patient_name = first_person
        
        assignment.display_patient_name = display_patient_name

        assignment.today_attendance = assignment.attendance_records.filter(
            date=today
        ).first()
        assignment.today_tasks_count = assignment.tasks.filter(
            due_date__date=today, status__in=["pending", "in_progress"]
        ).count()
        assignment.pending_tasks_count = assignment.tasks.filter(
            status__in=["pending", "in_progress"]
        ).count()
        assignment.unread_notes_count = assignment.care_notes.filter(
            read_by_caretaker=False
        ).count()

    context = {
        "assignments": assignments,
    }
    return render(request, "assignments/caretaker_assignments.html", context)


@login_required
@login_required
def family_assignment_detail(request, assignment_id):
    """Detailed view of an assignment for family"""
    if request.user.role != "family":
        messages.error(request, "Access denied.")
        return redirect("users:index")

    assignment = get_object_or_404(
        CareAssignment.objects.select_related(
            "caretaker", "caretaker__caretaker_profile"
        ),
        id=assignment_id,
        family=request.user,
    )
    today = timezone.localdate()
    date_str = request.GET.get("date", "")
    selected_date = today
    if date_str:
        try:
            selected_date = timezone.datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            selected_date = today
    else:
        # Default to start date if the assignment hasn't started yet
        if assignment.start_date and assignment.start_date > today:
            selected_date = assignment.start_date

    # Get recent data
    recent_reports = assignment.daily_reports.all()[:7]
    recent_notes = assignment.care_notes.all()[:10]

    # Task categorization for Family
    all_tasks = assignment.tasks.all().order_by("due_date")

    # Calculate flags for UI accountability
    now = timezone.now()
    for task in all_tasks:
        task.is_overdue = task.due_date < now
        task.is_locked = task.due_date.date() < now.date()
        task.is_missed = (
            task.is_locked and task.status != "completed" and task.status != "verified"
        )

    tasks_today = all_tasks.filter(due_date__date=selected_date)
    # Tasks that Caretaker finished but Family hasn't verified yet
    tasks_need_verification = all_tasks.filter(status="completed").order_by("due_date")
    tasks_past = (
        all_tasks.filter(due_date__date__lt=selected_date)
        .exclude(status="completed")
        .order_by("-due_date")
    )
    tasks_future = (
        all_tasks.filter(due_date__date__gt=selected_date)
        .exclude(status="completed")
        .order_by("due_date")
    )

    # Calculate attendance summary
    all_attendance = assignment.attendance_records.all()
    present_days = all_attendance.filter(status='present').count()
    absent_days = all_attendance.filter(status='absent').count()
    late_days = all_attendance.filter(status='late').count()
    leave_days = all_attendance.filter(status='leave').count()
    total_days = all_attendance.count()
    
    attendance_percentage = (present_days / total_days * 100) if total_days > 0 else 0
    
    attendance_summary = {
        'present_days': present_days,
        'absent_days': absent_days,
        'late_days': late_days,
        'leave_days': leave_days,
        'attendance_percentage': attendance_percentage
    }
    
    # Calculate week attendance
    start_of_week = today - timedelta(days=today.weekday())
    week_attendance = []
    for i in range(7):
        current_date = start_of_week + timedelta(days=i)
        record = all_attendance.filter(date=current_date).first()
        week_attendance.append({
            'date': current_date,
            'status': record.status if record else 'pending'
        })

    context = {
        "assignment": assignment,
        "recent_reports": recent_reports,
        "tasks_today": tasks_today,
        "tasks_need_verification": tasks_need_verification,
        "tasks_past": tasks_past,
        "tasks_future": tasks_future,
        "selected_date": selected_date,
        "is_today": selected_date == today,
        "recent_notes": recent_notes,
        "attendance_summary": attendance_summary,
        "week_attendance": week_attendance,
        "today": today,
    }
    return render(request, "assignments/family_assignment_detail.html", context)


@login_required
def caretaker_assignment_detail(request, assignment_id):
    """Detailed view of an assignment for caretaker"""
    if request.user.role != "caretaker":
        messages.error(request, "Access denied.")
        return redirect("users:index")

    # Determine base template
    base_template = "users/nurse_base.html"

    assignment = get_object_or_404(
        CareAssignment.objects.select_related(
            "family", "care_request", "care_request__elder_profile"
        ),
        id=assignment_id,
        caretaker=request.user,
    )

    today = timezone.now().date()
    
    # Get today's attendance
    today_attendance = assignment.attendance_records.filter(date=today).first()
    
    # Get tasks
    pending_tasks = assignment.tasks.filter(status__in=['pending', 'in_progress']).order_by('due_date')
    completed_tasks = assignment.tasks.filter(status__in=['completed', 'verified']).order_by('-completed_at')[:5]

    # Add is_overdue property to tasks
    for task in pending_tasks:
        task.is_overdue = task.due_date < timezone.now()

    # Check if report already submitted today
    today_report = assignment.daily_reports.filter(report_date=today).first()

    # Process patient name to be "single" if it contains multiple names (e.g. Ramesh & Savitri Sharma)
    patient_name = assignment.care_request.elder_profile.name if (assignment.care_request.elder_profile and assignment.care_request.elder_profile.name) else assignment.care_request.patient_name
    
    display_patient_name = patient_name
    if " & " in patient_name:
        parts = patient_name.split(" & ")
        first_person = parts[0].strip()
        last_person = parts[-1].strip()
        # Handle case like "Ramesh & Savitri Sharma" -> "Ramesh Sharma"
        if " " not in first_person and " " in last_person:
            last_name = last_person.split(" ")[-1]
            display_patient_name = f"{first_person} {last_name}"
        else:
            display_patient_name = first_person
    elif " and " in patient_name:
        parts = patient_name.split(" and ")
        first_person = parts[0].strip()
        last_person = parts[-1].strip()
        if " " not in first_person and " " in last_person:
            last_name = last_person.split(" ")[-1]
            display_patient_name = f"{first_person} {last_name}"
        else:
            display_patient_name = first_person

    context = {
        "assignment": assignment,
        "display_patient_name": display_patient_name,
        "today_attendance": today_attendance,
        "pending_tasks": pending_tasks,
        "completed_tasks": completed_tasks,
        "today_report": today_report,
        "base_template": base_template,
    }
    return render(request, "assignments/caretaker_assignment_detail.html", context)


@login_required
def terminate_assignment(request, assignment_id):
    """Terminate an assignment and allow family to leave a review"""
    if request.user.role != "family":
        messages.error(request, "Access denied.")
        return redirect("users:index")

    assignment = get_object_or_404(
        CareAssignment, id=assignment_id, family=request.user
    )

    if request.method == "POST":
        # Get form data
        termination_reason = request.POST.get("reason", "")
        rating = request.POST.get("rating")
        review_text = request.POST.get("review_text", "")

        # Validate rating
        if not rating:
            messages.error(request, "Please provide a rating to complete termination.")
            return redirect(
                "assignments:terminate_assignment", assignment_id=assignment.id
            )

        # Update assignment
        assignment.status = "terminated"
        assignment.termination_reason = termination_reason
        assignment.termination_date = date.today()
        assignment.end_date = date.today()
        assignment.save()

        # Create review
        from .models import CaregiverReview

        CaregiverReview.objects.create(
            assignment=assignment,
            caregiver=assignment.caretaker,
            family=request.user,
            rating=int(rating),
            review_text=review_text,
        )

        messages.success(
            request,
            f"✓ Assignment terminated. Thank you for rating {assignment.caretaker.get_full_name()} {rating} stars!",
        )
        return redirect("assignments:my_caregivers")

    context = {
        "assignment": assignment,
    }
    return render(request, "assignments/terminate_assignment.html", context)


# ============================================================================
# DAILY CARE REPORTS
# ============================================================================


@login_required
def create_daily_report(request, assignment_id):
    """Create daily care report (Caretaker)"""
    if request.user.role != "caretaker":
        messages.error(request, "Access denied.")
        return redirect("users:index")

    assignment = get_object_or_404(
        CareAssignment, id=assignment_id, caretaker=request.user, status="active"
    )

    # Check if report already exists for today
    today = timezone.now().date()
    
    # Validation 1: Prevent submission before the assignment has officially started
    if assignment.start_date and today < assignment.start_date:
        messages.error(request, "You cannot submit reports before the assignment starts.")
        return redirect("assignments:caretaker_assignment_detail", assignment_id=assignment.id)
        
    # Validation 2: Ensure the caretaker has checked in today before submitting a report
    today_attendance = assignment.attendance_records.filter(date=today, status='present').first()
    if not today_attendance or not today_attendance.check_in_time:
        messages.error(request, "You must check in for your shift before submitting a daily care report.")
        return redirect("assignments:caretaker_assignment_detail", assignment_id=assignment.id)
        
    existing_report = assignment.daily_reports.filter(report_date=today).first()

    if request.method == "POST":
        try:
            if existing_report:
                report = existing_report
            else:
                report = DailyCareReport(assignment=assignment, report_date=today)

            # Vital Signs
            report.blood_pressure_systolic = (
                request.POST.get("blood_pressure_systolic") or None
            )
            report.blood_pressure_diastolic = (
                request.POST.get("blood_pressure_diastolic") or None
            )
            report.heart_rate = request.POST.get("heart_rate") or None
            report.temperature = request.POST.get("temperature") or None
            report.blood_sugar = request.POST.get("blood_sugar") or None
            report.oxygen_saturation = request.POST.get("oxygen_saturation") or None
            report.weight = request.POST.get("weight") or None

            # Activities
            report.meals_taken = request.POST.get("meals_taken", "")
            report.water_intake = request.POST.get("water_intake", "")
            report.sleep_hours = request.POST.get("sleep_hours") or None
            report.sleep_quality = request.POST.get("sleep_quality", "")
            report.mood = request.POST.get("mood", "")

            # Care activities
            report.medications_given = request.POST.get("medications_given", "")
            report.exercises_done = request.POST.get("exercises_done", "")
            report.activities_done = request.POST.get("activities_done", "")

            # Observations
            report.observations = request.POST.get("observations", "")
            report.concerns = request.POST.get("concerns", "")
            report.recommendations = request.POST.get("recommendations", "")

            # Photo
            if "photo" in request.FILES:
                report.photo = request.FILES["photo"]

            report.save()

            messages.success(request, "Daily care report submitted successfully!")
            return redirect(
                "assignments:create_daily_report", assignment_id=assignment.id
            )

        except Exception as e:
            messages.error(request, f"Error submitting report: {str(e)}")

    context = {
        "assignment": assignment,
        "report": existing_report,
        "mood_choices": DailyCareReport.MOOD_CHOICES,
        "sleep_quality_choices": DailyCareReport._meta.get_field(
            "sleep_quality"
        ).choices,
    }
    return render(request, "assignments/create_daily_report.html", context)


@login_required
def view_reports(request, assignment_id):
    """View all daily reports (Family)"""
    if request.user.role != "family":
        messages.error(request, "Access denied.")
        return redirect("users:index")

    assignment = get_object_or_404(
        CareAssignment, id=assignment_id, family=request.user
    )

    # Mark reports as read
    unread_reports = assignment.daily_reports.filter(family_read=False)
    for report in unread_reports:
        report.family_read = True
        report.read_at = timezone.now()
        report.save()

    # Filter by date range
    start_date = request.GET.get("start_date")
    end_date = request.GET.get("end_date")

    reports = assignment.daily_reports.all()

    if start_date:
        reports = reports.filter(report_date__gte=start_date)
    if end_date:
        reports = reports.filter(report_date__lte=end_date)

    # Statistics
    stats = reports.aggregate(
        avg_heart_rate=Avg("heart_rate"),
        avg_sleep=Avg("sleep_hours"),
        total_reports=Count("id"),
        reports_with_concerns=Count(
            "id", filter=Q(concerns__isnull=False) & ~Q(concerns="")
        ),
    )

    base_template = (
        "users/nurse_base.html"
        if request.user.role == "caretaker"
        else "users/family_base.html"
    )

    context = {
        "assignment": assignment,
        "reports": reports,
        "stats": stats,
        "base_template": base_template,
    }
    return render(request, "assignments/view_reports.html", context)


@login_required
def report_detail(request, report_id):
    """View single report detail"""
    report = get_object_or_404(DailyCareReport, id=report_id)

    # Check permission
    if (
        request.user != report.assignment.family
        and request.user != report.assignment.caretaker
    ):
        messages.error(request, "Access denied.")
        return redirect("users:index")

    # Mark as read if family
    if request.user.role == "family" and not report.family_read:
        report.family_read = True
        report.read_at = timezone.now()
        report.save()

    base_template = (
        "users/nurse_base.html"
        if request.user.role == "caretaker"
        else "users/family_base.html"
    )

    context = {
        "report": report,
        "base_template": base_template,
    }
    return render(request, "assignments/report_detail.html", context)


@login_required
def add_family_notes(request, report_id):
    """Add family notes to a report"""
    report = get_object_or_404(
        DailyCareReport, id=report_id, assignment__family=request.user
    )

    if request.method == "POST":
        report.family_notes = request.POST.get("family_notes", "")
        report.save()
        messages.success(request, "Notes added successfully!")
        return redirect("assignments:report_detail", report_id=report.id)

    return redirect("assignments:report_detail", report_id=report.id)


# ============================================================================
# TASKS MANAGEMENT
# ============================================================================


@login_required
def create_task(request, assignment_id):
    """Create task for caretaker (Family)"""
    if request.user.role != "family":
        messages.error(request, "Access denied.")
        return redirect("users:index")

    assignment = get_object_or_404(
        CareAssignment, id=assignment_id, family=request.user, status="active"
    )

    if request.method == "POST":
        try:
            # Get common task details
            title = request.POST.get("title")
            description = request.POST.get("description")
            priority = request.POST.get("priority", "medium")

            # Start date/time
            due_date_str = request.POST.get("due_date")
            if due_date_str:
                if len(due_date_str) > 16:
                    due_date_str = due_date_str[:16]
                start_datetime = datetime.strptime(due_date_str, "%Y-%m-%dT%H:%M")
            else:
                start_datetime = timezone.now() + timedelta(days=1)

            # Use localized timezone if possible
            if timezone.is_naive(start_datetime):
                start_datetime = timezone.make_aware(start_datetime)
                
            # Prevent tasks before assignment start date
            if assignment.start_date and start_datetime.date() < assignment.start_date:
                messages.error(request, f"Tasks cannot be scheduled before the assignment start date ({assignment.start_date}).")
                return redirect("assignments:family_assignment_detail", assignment_id=assignment.id)

            # Prevent tasks outside of working hours
            if assignment.application and assignment.application.work_start_time and assignment.application.work_end_time:
                task_time = start_datetime.time()
                work_start = assignment.application.work_start_time
                work_end = assignment.application.work_end_time
                
                is_valid_time = False
                if work_start <= work_end:
                    is_valid_time = work_start <= task_time <= work_end
                else:
                    # Overnight shift (e.g., 22:00 to 06:00)
                    is_valid_time = task_time >= work_start or task_time <= work_end
                    
                if not is_valid_time:
                    messages.error(request, f"Tasks must be scheduled during the caretaker's working hours ({work_start.strftime('%I:%M %p')} to {work_end.strftime('%I:%M %p')}).")
                    return redirect("assignments:family_assignment_detail", assignment_id=assignment.id)

            # Check for recurring options
            is_recurring = request.POST.get("is_recurring") == "on"

            if is_recurring:
                end_date_str = request.POST.get("end_date")
                if not end_date_str:
                    messages.error(
                        request, "Please provide an end date for recurring tasks."
                    )
                    return redirect(
                        "assignments:family_assignment_detail",
                        assignment_id=assignment.id,
                    )

                # We interpret end_date as the last day to create tasks for
                end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()

                # Selected days of week (if any)
                selected_days = request.POST.getlist(
                    "days_of_week"
                )  # ['0', '1', ...] where 0 is Monday

                current_datetime = start_datetime
                tasks_created = 0

                while current_datetime.date() <= end_date:
                    # If specific days are selected, check if current day is one of them
                    # weekday() returns 0 for Monday, 6 for Sunday
                    if (
                        not selected_days
                        or str(current_datetime.weekday()) in selected_days
                    ):
                        CareTask.objects.create(
                            assignment=assignment,
                            title=title,
                            description=description,
                            priority=priority,
                            due_date=current_datetime,
                            assigned_by=request.user,
                        )
                        tasks_created += 1

                    # Move to next day
                    current_datetime += timedelta(days=1)

                if tasks_created > 0:
                    # Create Notification
                    Notification.objects.create(
                        recipient=assignment.caretaker,
                        sender=request.user,
                        notification_type="task_assigned",
                        title=f"{tasks_created} New Tasks Assigned",
                        message=f"New tasks have been assigned to you for {title} from {start_datetime.date()} to {end_date}.",
                        icon="fa-tasks",
                        link=f"/assignments/caretaker/{assignment.id}/",
                    )
                    messages.success(
                        request,
                        f"Successfully created {tasks_created} tasks from {start_datetime.date()} to {end_date}.",
                    )
                else:
                    messages.warning(
                        request,
                        "No tasks were created. Check your date range and selected days.",
                    )
            else:
                # Single task creation (standard behavior)
                task = CareTask.objects.create(
                    assignment=assignment,
                    title=title,
                    description=description,
                    priority=priority,
                    due_date=start_datetime,
                    assigned_by=request.user,
                )

                # Create Notification for single task
                Notification.objects.create(
                    recipient=assignment.caretaker,
                    sender=request.user,
                    notification_type="task_assigned",
                    title="New Task Assigned",
                    message=f"A new task '{title}' has been assigned to you for {start_datetime.strftime('%b %d, %H:%M')}.",
                    icon="fa-tasks",
                    link=f"/assignments/caretaker/{assignment.id}/",
                )

                messages.success(request, f"Task '{task.title}' created successfully!")

            return redirect(
                "assignments:family_assignment_detail", assignment_id=assignment.id
            )

        except Exception as e:
            messages.error(request, f"Error creating task(s): {str(e)}")

    context = {
        "assignment": assignment,
        "priority_choices": CareTask.PRIORITY_CHOICES,
    }
    return render(request, "assignments/create_task.html", context)


@login_required
def edit_task(request, task_id):
    """Edit an existing task (Family Only)"""
    task = get_object_or_404(CareTask, id=task_id)

    # Permission: Only family who assigned/owns the task
    if request.user != task.assignment.family:
        messages.error(request, "Access denied. Only families can edit task details.")
        return redirect("users:index")

    if request.method == "POST":
        task.title = request.POST.get("title", task.title)
        task.description = request.POST.get("description", task.description)
        task.priority = request.POST.get("priority", task.priority)

        due_date_str = request.POST.get("due_date")
        if due_date_str:
            try:
                # Truncate seconds or milliseconds added by some browsers
                if len(due_date_str) > 16:
                    due_date_str = due_date_str[:16]

                dt = timezone.datetime.strptime(due_date_str, "%Y-%m-%dT%H:%M")
                task.due_date = timezone.make_aware(dt)
            except ValueError:
                pass

        task.save()
        messages.success(request, f"Task '{task.title}' updated successfully.")

        # Redirect back (preserving context)
        referer = request.META.get("HTTP_REFERER", "")
        if referer and "date=" in referer:
            return redirect(referer)
        return redirect("assignments:task_list", assignment_id=task.assignment.id)

    # For GET, we'll return JSON for the modal
    from django.http import JsonResponse

    return JsonResponse(
        {
            "id": task.id,
            "title": task.title,
            "description": task.description,
            "priority": task.priority,
            "due_date": (
                timezone.localtime(task.due_date).strftime("%Y-%m-%dT%H:%M")
                if task.due_date
                else ""
            ),
        }
    )


@login_required
def task_details(request, task_id):
    """Return task details as JSON (Family Only)"""
    task = get_object_or_404(CareTask, id=task_id)

    # Permission: Only family who assigned/owns the task
    if request.user != task.assignment.family:
        return JsonResponse({"error": "Unauthorized"}, status=403)

    return JsonResponse(
        {
            "id": task.id,
            "title": task.title,
            "description": task.description,
            "priority": task.priority,
            "due_date": (
                timezone.localtime(task.due_date).strftime("%Y-%m-%dT%H:%M")
                if task.due_date
                else ""
            ),
        }
    )


@login_required
def delete_task(request, task_id):
    """Delete a task (Family Only)"""
    task = get_object_or_404(CareTask, id=task_id)

    # Permission: Only family who assigned/owns the task
    if request.user != task.assignment.family:
        messages.error(request, "Access denied. Only families can delete tasks.")
        return redirect("users:index")

    if request.method == "POST":
        task_title = task.title
        assignment_id = task.assignment.id
        task.delete()
        messages.success(request, f"Task '{task_title}' was successfully deleted.")
        
        # Redirect back (preserving context if possible)
        referer = request.META.get("HTTP_REFERER", "")
        if referer:
            return redirect(referer)
        return redirect("assignments:task_list", assignment_id=assignment_id)
        
    # Redirect if accessed via GET
    return redirect("assignments:family_assignment_detail", assignment_id=task.assignment.id)


@login_required
def update_task_status(request, task_id):
    """Update task status (Caretaker) with Proof of Work support"""
    task = get_object_or_404(CareTask, id=task_id)

    if request.user != task.assignment.caretaker:
        messages.error(request, "Access denied.")
        return redirect("users:index")

    if request.method == "POST":
        # Restriction: Cannot update tasks from previous days or future days
        now = timezone.now()
        task_date = task.due_date.date()

        if task_date < now.date():
            messages.error(
                request,
                f"Review period for '{task.title}' has expired. Past tasks cannot be updated.",
            )
            referer = request.META.get("HTTP_REFERER", "")
            if referer and "date=" in referer:
                return redirect(referer)
            return redirect("assignments:task_list", assignment_id=task.assignment.id)

        if task_date > now.date():
            messages.error(
                request,
                f"Cannot update '{task.title}' as it's scheduled for a future date ({task_date.strftime('%b %d, %Y')}). Tasks can only be updated on the care date.",
            )
            referer = request.META.get("HTTP_REFERER", "")
            if referer and "date=" in referer:
                return redirect(referer)
            return redirect("assignments:task_list", assignment_id=task.assignment.id)

        status = request.POST.get("status")
        notes = request.POST.get("notes", "")
        proof_image = request.FILES.get("proof_image")

        task.status = status
        task.caretaker_notes = notes

        if status == "completed":
            task.completed_at = timezone.now()
            if proof_image:
                task.proof_image = proof_image

        task.save()

        # Log successful update
        messages.success(request, f"Task '{task.title}' marked as {status}.")

        # Reset escalation if completed
        if status == "completed":
            task.escalation_level = 0
            task.save()

        # Redirect back to the same page (preserving date filter if possible)
        referer = request.META.get("HTTP_REFERER", "")
        if referer and "date=" in referer:
            return redirect(referer)

        return redirect("assignments:task_list", assignment_id=task.assignment.id)


@login_required
def verify_task(request, task_id):
    """Verify a completed task (Family/Nurse/Admin)"""
    task = get_object_or_404(CareTask, id=task_id)

    # Permission: Family or Nurse/Admin only
    if request.user != task.assignment.family and request.user.role not in [
        "nurse",
        "admin",
        "coordinator",
    ]:
        messages.error(
            request, "Access denied. Only families or nurses can verify tasks."
        )
        return redirect("users:index")

    if task.status != "completed":
        messages.warning(
            request,
            f"Task '{task.title}' is not in a completed state for verification.",
        )
    else:
        task.status = "verified"
        task.save()
        messages.success(
            request, f"Task '{task.title}' has been successfully verified."
        )

    # Redirect back (preserving context if possible)
    referer = request.META.get("HTTP_REFERER", "")
    if referer and "date=" in referer:
        return redirect(referer)
    return redirect("assignments:task_list", assignment_id=task.assignment.id)


def check_missed_tasks(request, assignment_id=None):
    """
    Check for overdue tasks and escalate notifications.
    Nurse (Caretaker) -> Family -> Admin
    """
    from apps.Notifications.models import Notification
    from django.db.models import Count

    now = timezone.now()
    filters = {"status__in": ["pending", "in_progress"]}
    if assignment_id:
        filters["assignment_id"] = assignment_id

    overdue_tasks = CareTask.objects.filter(due_date__lt=now, **filters)

    for task in overdue_tasks:
        time_overdue = now - task.due_date
        assignment = task.assignment

        # Level 1: Overdue by > 1 hour -> Notify Nurse (Caretaker)
        if time_overdue > timedelta(hours=1) and task.escalation_level == 0:
            Notification.objects.create(
                recipient=assignment.caretaker,
                notification_type="reminder",
                title=f"Missed Task: {task.title}",
                message=f"The task '{task.title}' for {assignment.care_request.patient_name} was due at {task.due_date.strftime('%H:%M')}. Please update status.",
                icon="exclamation-circle",
                link=f"/assignments/{assignment.id}/tasks/",
            )
            task.escalation_level = 1
            task.save()

        # Level 2: Still not done after 4 hours -> Notify Family
        elif time_overdue > timedelta(hours=4) and task.escalation_level == 1:
            Notification.objects.create(
                recipient=assignment.family,
                notification_type="reminder",
                title=f"Urgent: Uncompleted Task",
                message=f"The task '{task.title}' assigned to {assignment.caretaker.get_full_name()} is significantly overdue.",
                icon="exclamation-triangle",
                link=f"/family/assignment/{assignment.id}/",
            )
            task.escalation_level = 2
            task.save()

        # Level 3: Severe delay (> 12 hours) -> Notify Admin
        elif time_overdue > timedelta(hours=12) and task.escalation_level == 2:
            admin_users = User.objects.filter(is_staff=True)
            for admin in admin_users:
                Notification.objects.create(
                    recipient=admin,
                    notification_type="reminder",
                    title=f"Admin Alert: Severe Delay",
                    message=f"Assignment {assignment.id}: Task '{task.title}' has been overdue for 12+ hours. Critical oversight required.",
                    icon="shield-alt",
                    link=f"/admin/assignments/caretask/{task.id}/change/",
                )
            task.escalation_level = 3
            task.save()

    # Repeated Pattern Check: If a caretaker has 3 or more tasks reach escalation Level 2 in a week
    if assignment_id:
        assignment = CareAssignment.objects.get(id=assignment_id)
        caretaker = assignment.caretaker
        one_week_ago = now - timedelta(days=7)
        
        missed_pattern_count = CareTask.objects.filter(
            assignment__caretaker=caretaker,
            escalation_level__gte=2,
            updated_at__gte=one_week_ago
        ).count()

        if missed_pattern_count >= 3:
            admin_users = User.objects.filter(is_staff=True)
            # Create a summary alert for admin if not already sent recently
            for admin in admin_users:
                # Check if we already sent a pattern alert today
                today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
                exists = Notification.objects.filter(
                    recipient=admin,
                    title="Admin Alert: Repeated Pattern of Missed Tasks",
                    created_at__gte=today_start
                ).exists()

                if not exists:
                    Notification.objects.create(
                        recipient=admin,
                        notification_type="reminder",
                        title="Admin Alert: Repeated Pattern of Missed Tasks",
                        message=f"Caretaker {caretaker.get_full_name()} has had {missed_pattern_count} tasks reach critical escalation levels in the last 7 days. Investigation recommended.",
                        icon="user-slash",
                        link=f"/admin/Users/user/{caretaker.id}/change/",
                    )

    return True


@login_required
def task_list(request, assignment_id):
    """List all tasks for an assignment"""
    assignment = get_object_or_404(CareAssignment, id=assignment_id)

    # Check permission
    if request.user != assignment.family and request.user != assignment.caretaker:
        messages.error(request, "Access denied.")
        return redirect("users:index")

    # Determine base template
    if request.user.role == "caretaker":
        base_template = "users/nurse_base.html"
    elif request.user.role == "family":
        base_template = "users/family_base.html"
    else:
        base_template = "base.html"

    # Filter by date in local project timezone
    today = timezone.localdate()
    date_str = request.GET.get("date", "")
    selected_date = None
    if date_str:
        try:
            selected_date = timezone.datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            selected_date = today
    else:
        selected_date = today

    # Status filter
    status_filter = request.GET.get("status", "")

    # Query tasks
    base_tasks = assignment.tasks.all().order_by("due_date")

    if status_filter:
        base_tasks = base_tasks.filter(status=status_filter)

    # Split into Today, Past, and Future
    tasks_today = base_tasks.filter(due_date__date=selected_date)
    tasks_past = base_tasks.filter(due_date__date__lt=selected_date).order_by(
        "-due_date"
    )
    tasks_future = base_tasks.filter(due_date__date__gt=selected_date).order_by(
        "due_date"
    )

    # Run missed task check (lazy execution)
    check_missed_tasks(request, assignment_id)

    # Calculate counts and flags for UI
    now = timezone.now()
    today_date = now.date()
    for task in base_tasks:
        task.is_overdue = task.due_date < now
        task.is_locked = task.due_date.date() < today_date
        task.is_missed = task.is_locked and task.status != "completed"

    missed_count = (
        base_tasks.filter(due_date__date__lt=now.date())
        .exclude(status="completed")
        .count()
    )

    context = {
        "assignment": assignment,
        "tasks_today": tasks_today,
        "tasks_past": tasks_past,
        "tasks_future": tasks_future,
        "selected_date": selected_date,
        "is_today": selected_date == today,
        "status_filter": status_filter,
        "total_tasks": base_tasks.count(),
        "pending_count": base_tasks.filter(status="pending").count(),
        "completed_count": base_tasks.filter(status="completed").count(),
        "missed_count": missed_count,
        "base_template": base_template,
    }
    return render(request, "assignments/task_list.html", context)


@login_required
def task_detail(request, task_id):
    """View task details"""
    task = get_object_or_404(CareTask, id=task_id)

    # Check permission
    if (
        request.user != task.assignment.family
        and request.user != task.assignment.caretaker
    ):
        messages.error(request, "Access denied.")
        return redirect("users:index")

    if request.method == "POST" and request.user == task.assignment.family:
        task.family_feedback = request.POST.get("feedback", "")
        task.save()
        messages.success(request, "Feedback added!")

    context = {
        "task": task,
    }
    return render(request, "assignments/task_detail.html", context)


# ============================================================================
# NOTES / MESSAGES MANAGEMENT
# ============================================================================

# @login_required
# def create_note(request, assignment_id):
#     """Create professional note (Both Family and Caretaker)"""
#     assignment = get_object_or_404(CareAssignment, id=assignment_id)

#     # Check permission
#     if request.user != assignment.family and request.user != assignment.caretaker:
#         messages.error(request, "Access denied.")
#         return redirect('users:index')

#     # Determine base template for the template
#     if request.user.role == 'caretaker':
#         base_template = 'users/nurse_base.html'
#     elif request.user.role == 'family':
#         base_template = 'users/family_base.html'
#     else:
#         base_template = 'base.html'

#     if request.method == 'POST':
#         try:
#             note = CareNote.objects.create(
#                 assignment=assignment,
#                 title=request.POST.get('title'),
#                 content=request.POST.get('content'),
#                 note_type=request.POST.get('note_type', 'general'),
#                 created_by=request.user,
#                 is_important=request.POST.get('is_important') == 'on',
#                 is_urgent=request.POST.get('is_urgent') == 'on'
#             )

#             messages.success(request, "Message sent successfully!")

#             if request.user.role == 'family':
#                 return redirect('assignments:family_assignment_detail', assignment_id=assignment.id)
#             else:
#                 return redirect('assignments:caretaker_assignment_detail', assignment_id=assignment.id)

#         except Exception as e:
#             messages.error(request, f"Error sending message: {str(e)}")

#     context = {
#         'assignment': assignment,
#         'note_types': CareNote.NOTE_TYPES,
#         'base_template': base_template,
#     }
#     return render(request, 'assignments/create_note.html', context)


@login_required
def create_note(request, assignment_id):
    """Create professional note (Both Family and Caretaker)"""
    assignment = get_object_or_404(CareAssignment, id=assignment_id)

    # Check permission
    if request.user != assignment.family and request.user != assignment.caretaker:
        messages.error(request, "Access denied.")
        return redirect("users:index")

    # Determine base template for the template
    if request.user.role == "caretaker":
        base_template = "users/nurse_base.html"
    elif request.user.role == "family":
        base_template = "users/family_base.html"
    else:
        base_template = "base.html"

    if request.method == "POST":
        try:
            title = request.POST.get("title")
            content = request.POST.get("content")

            if not title or not content:
                messages.error(
                    request, "Please provide both title and message content."
                )
                # Redirect back to conversation view
                return redirect("assignments:note_list", assignment_id=assignment.id)

            note = CareNote.objects.create(
                assignment=assignment,
                title=title,
                content=content,
                note_type=request.POST.get("note_type", "general"),
                created_by=request.user,
                is_important=request.POST.get("is_important") == "on",
                is_urgent=request.POST.get("is_urgent") == "on",
            )

            messages.success(request, "Message sent successfully!")

            # FIXED: Redirect to the conversation view (note_list) instead of assignment detail
            return redirect("assignments:note_list", assignment_id=assignment.id)

        except Exception as e:
            messages.error(request, f"Error sending message: {str(e)}")
            return redirect("assignments:note_list", assignment_id=assignment.id)

    context = {
        "assignment": assignment,
        "note_types": CareNote.NOTE_TYPES,
        "base_template": base_template,
    }
    return render(request, "assignments/create_note.html", context)


@login_required
def note_list(request, assignment_id):
    """List all notes for an assignment (conversation view)"""
    assignment = get_object_or_404(CareAssignment, id=assignment_id)

    # Check permission
    if request.user != assignment.family and request.user != assignment.caretaker:
        messages.error(request, "Access denied.")
        return redirect("users:index")

    # Get all notes
    all_notes = assignment.care_notes.all().order_by("-created_at")

    # Separate received and sent messages
    received_messages = []
    sent_messages = []

    for note in all_notes:
        # Mark read status for the current user
        if request.user.role == "family":
            is_read = note.read_by_family
            if note.created_by != request.user and not is_read:
                note.read_by_family = True
                note.read_at = timezone.now()
                note.save()
                is_read = True
        else:
            is_read = note.read_by_caretaker
            if note.created_by != request.user and not is_read:
                note.read_by_caretaker = True
                note.read_at = timezone.now()
                note.save()
                is_read = True

        note.is_read_by_user = is_read

        # Separate into received and sent
        if note.created_by == request.user:
            sent_messages.append(note)
        else:
            received_messages.append(note)

    # Pagination for received messages
    received_paginator = Paginator(received_messages, 20)
    received_page = request.GET.get("received_page", 1)
    received_page_obj = received_paginator.get_page(received_page)

    # Pagination for sent messages
    sent_paginator = Paginator(sent_messages, 20)
    sent_page = request.GET.get("sent_page", 1)
    sent_page_obj = sent_paginator.get_page(sent_page)

    # Determine base template
    if request.user.role == "caretaker":
        base_template = "users/nurse_base.html"
    elif request.user.role == "family":
        base_template = "users/family_base.html"
    else:
        base_template = "base.html"

    context = {
        "assignment": assignment,
        "received_messages": received_page_obj,
        "sent_messages": sent_page_obj,
        "received_count": len(received_messages),
        "sent_count": len(sent_messages),
        "base_template": base_template,
    }
    return render(request, "assignments/note_list.html", context)


@login_required
def note_detail(request, note_id):
    """View single note details"""
    note = get_object_or_404(CareNote, id=note_id)

    # Check permission
    if (
        request.user != note.assignment.family
        and request.user != note.assignment.caretaker
    ):
        messages.error(request, "Access denied.")
        return redirect("users:index")

    # Mark as read
    if request.user.role == "family" and not note.read_by_family:
        note.read_by_family = True
        note.read_at = timezone.now()
        note.save()
    elif request.user.role == "caretaker" and not note.read_by_caretaker:
        note.read_by_caretaker = True
        note.read_at = timezone.now()
        note.save()

    context = {
        "note": note,
    }
    return render(request, "assignments/note_detail.html", context)


@login_required
def my_messages(request):
    """View all messages across all assignments (inbox)"""

    if request.user.role == "caretaker":
        messages = CareNote.objects.filter(
            assignment__caretaker=request.user
        ).select_related(
            "assignment", "created_by", "assignment__family", "assignment__caretaker"
        )

    elif request.user.role == "family":
        messages = CareNote.objects.filter(
            assignment__family=request.user
        ).select_related(
            "assignment", "created_by", "assignment__family", "assignment__caretaker"
        )

    else:
        messages = CareNote.objects.none()

    # Mark unread messages for current user and add is_read_by_user property
    for msg in messages:
        if request.user.role == "family":
            msg.is_read_by_user = msg.read_by_family
        else:
            msg.is_read_by_user = msg.read_by_caretaker

    unread_count = sum(1 for msg in messages if not msg.is_read_by_user)

    # Group messages by assignment
    messages_by_assignment = {}
    for msg in messages:
        if msg.assignment.id not in messages_by_assignment:
            messages_by_assignment[msg.assignment.id] = {
                "assignment": msg.assignment,
                "messages": [],
                "unread_count": 0,
                "last_message": msg,
            }
        messages_by_assignment[msg.assignment.id]["messages"].append(msg)
        if not msg.is_read_by_user:
            messages_by_assignment[msg.assignment.id]["unread_count"] += 1

        # Update last message if newer
        if (
            msg.created_at
            > messages_by_assignment[msg.assignment.id]["last_message"].created_at
        ):
            messages_by_assignment[msg.assignment.id]["last_message"] = msg

    # FIXED: Sort conversations - URGENT first, then IMPORTANT, then most recent
    conversations = sorted(
        messages_by_assignment.values(),
        key=lambda x: (
            not x["last_message"].is_urgent,  # Urgent conversations first
            not x["last_message"].is_important,  # Then important
            -x["last_message"].created_at.timestamp(),  # Then most recent
        ),
    )

    # Pagination
    paginator = Paginator(conversations, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    if request.user.role == "caretaker":
        base_template = "users/nurse_base.html"
    else:
        base_template = "users/family_base.html"

    context = {
        "conversations": page_obj,
        "unread_messages_count": unread_count,
        "base_template": base_template,
    }
    return render(request, "assignments/my_messages.html", context)


@login_required
def mark_note_read(request, note_id):
    """Mark a single note as read"""
    note = get_object_or_404(CareNote, id=note_id)

    # Check permission
    if (
        request.user != note.assignment.family
        and request.user != note.assignment.caretaker
    ):
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"error": "Access denied"}, status=403)
        messages.error(request, "Access denied.")
        return redirect("users:index")

    if request.method == "POST":
        if request.user.role == "family":
            note.read_by_family = True
        else:
            note.read_by_caretaker = True
        note.read_at = timezone.now()
        note.save()

        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"success": True})

        messages.success(request, "Message marked as read.")
        return redirect("assignments:note_list", assignment_id=note.assignment.id)

    return redirect("assignments:note_list", assignment_id=note.assignment.id)


@login_required
def delete_note(request, note_id):
    """Delete a note"""
    note = get_object_or_404(CareNote, id=note_id)

    # Check permission (only sender can delete)
    if request.user != note.created_by:
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse(
                {"error": "You can only delete your own messages"}, status=403
            )
        messages.error(request, "You can only delete your own messages.")
        return redirect("assignments:note_list", assignment_id=note.assignment.id)

    if request.method == "POST":
        assignment_id = note.assignment.id
        note.delete()
        messages.success(request, "Message deleted successfully.")

        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"success": True})

        return redirect("assignments:note_list", assignment_id=assignment_id)

    return redirect("assignments:note_list", assignment_id=note.assignment.id)


# ============================================================================
# ATTENDANCE MANAGEMENT
# ============================================================================


@login_required
def mark_attendance(request, assignment_id):
    """Mark attendance (Caretaker)"""
    if request.user.role != "caretaker":
        messages.error(request, "Access denied.")
        return redirect("users:index")

    assignment = get_object_or_404(
        CareAssignment, id=assignment_id, caretaker=request.user, status="active"
    )

    today = date.today()
    attendance = Attendance.objects.filter(assignment=assignment, date=today).first()

    if request.method == "POST":
        action = request.POST.get("action")
        current_time = datetime.now().time()

        # Prevent check-in for future dates
        if action == "check_in":
            # Get the target date from form or use today
            check_date_str = request.POST.get("check_date", "")
            if check_date_str:
                try:
                    check_date = datetime.strptime(check_date_str, "%Y-%m-%d").date()
                except ValueError:
                    check_date = today
            else:
                check_date = today

            if check_date > today:
                messages.error(
                    request,
                    f"Cannot check-in for future date ({check_date.strftime('%b %d, %Y')}). Check-in is only allowed on the actual care date.",
                )
                return redirect(
                    "assignments:caretaker_assignment_detail",
                    assignment_id=assignment.id,
                )

        # Ensure attendance record exists for actions
        if not attendance:
            attendance = Attendance(
                assignment=assignment,
                date=today,
                status="present",  # Default but will be changed by action
            )

        if action == "check_in":
            if not attendance.check_in_time:
                # Check if too early (before expected start time)
                if assignment.application and assignment.application.work_start_time:
                    expected_start = assignment.application.work_start_time
                else:
                    expected_start = datetime.strptime("09:00", "%H:%M").time()
                current_datetime = datetime.combine(today, current_time)
                expected_start_datetime = datetime.combine(today, expected_start)

                if current_datetime < expected_start_datetime:
                    minutes_early = (
                        expected_start_datetime - current_datetime
                    ).seconds // 60
                    messages.error(
                        request,
                        f"⚠️ Too early to check-in! Care starts at {expected_start.strftime('%I:%M %p')}. You're {minutes_early} minutes early.",
                    )
                    return redirect(
                        "assignments:caretaker_assignment_detail",
                        assignment_id=assignment.id,
                    )

                attendance.check_in_time = current_time
                attendance.status = "present"
                attendance.check_in_location = request.POST.get("location", "")

                # Check if late (assuming 9 AM start time)
                if current_time > expected_start:
                    attendance.late_minutes = (
                        datetime.combine(today, current_time)
                        - datetime.combine(today, expected_start)
                    ).seconds // 60
                    messages.warning(
                        request,
                        f"⚠️ You checked in late by {attendance.late_minutes} minutes!",
                    )

                    # Notify family about late check-in
                    from apps.Notifications.models import Notification

                    Notification.objects.create(
                        recipient=assignment.family,
                        sender=request.user,
                        notification_type="attendance",
                        title="Late Check-in Alert",
                        message=f'{request.user.get_full_name()} checked in late today at {current_time.strftime("%I:%M %p")} ({attendance.late_minutes} mins late)',
                        icon="fa-clock",
                        link=f"/assignments/family/{assignment.id}/",
                        is_read=False,
                    )
                else:
                    messages.success(
                        request, f"✅ Checked in at {current_time.strftime('%I:%M %p')}"
                    )

                attendance.save()
                return redirect(
                    "assignments:caretaker_assignment_detail",
                    assignment_id=assignment.id,
                )
            else:
                messages.warning(request, "Already checked in today!")

        elif action == "check_out":
            if (
                attendance
                and attendance.check_in_time
                and not attendance.check_out_time
            ):
                attendance.check_out_time = current_time
                attendance.check_out_location = request.POST.get("location", "")
                attendance.calculate_work_hours()

                # Check if leaving early (assuming 5 PM end time)
                expected_end = datetime.strptime("17:00", "%H:%M").time()
                if current_time < expected_end:
                    early_minutes = (
                        datetime.combine(today, expected_end)
                        - datetime.combine(today, current_time)
                    ).seconds // 60
                    messages.warning(
                        request,
                        f"⚠️ You are checking out early by {early_minutes} minutes!",
                    )

                    # Notify family about early checkout
                    from apps.Notifications.models import Notification

                    Notification.objects.create(
                        recipient=assignment.family,
                        sender=request.user,
                        notification_type="attendance",
                        title="Early Checkout Alert",
                        message=f'{request.user.get_full_name()} checked out early at {current_time.strftime("%I:%M %p")} ({early_minutes} mins early)',
                        icon="fa-clock",
                        link=f"/assignments/family/{assignment.id}/",
                        is_read=False,
                    )
                else:
                    messages.success(
                        request,
                        f"✅ Checked out at {current_time.strftime('%I:%M %p')}",
                    )

                messages.info(
                    request,
                    f"📊 Hours worked today: {attendance.actual_hours_worked:.2f} hours",
                )

                attendance.save()
                return redirect("dashboard:caretaker_dashboard")
            else:
                messages.warning(request, "Check-in first or already checked out!")

        elif action == "mark_absent":
            attendance.status = "absent"
            attendance.notes = request.POST.get("notes", "")
            attendance.save()

            # Notify family about absence (URGENT)
            from apps.Notifications.models import Notification

            Notification.objects.create(
                recipient=assignment.family,
                sender=request.user,
                notification_type="attendance",
                title="⚠️ URGENT: Caregiver Absent Today!",
                message=f"{request.user.get_full_name()} marked ABSENT today. Reason: {attendance.notes}. Please arrange backup care immediately.",
                icon="fa-exclamation-triangle",
                link=f"/assignments/family/{assignment.id}/",
                is_read=False,
            )

            messages.info(
                request, "Marked as absent. Family has been notified urgently."
            )
            return redirect("dashboard:caretaker_dashboard")

        elif action == "mark_leave":
            attendance.status = "leave"
            attendance.notes = request.POST.get("notes", "")
            attendance.save()

            # Notify family about leave (INFORMATIONAL)
            from apps.Notifications.models import Notification

            Notification.objects.create(
                recipient=assignment.family,
                sender=request.user,
                notification_type="attendance",
                title="Caregiver on Leave Today",
                message=f"{request.user.get_full_name()} is on LEAVE today. Reason: {attendance.notes}",
                icon="fa-umbrella-beach",
                link=f"/assignments/family/{assignment.id}/",
                is_read=False,
            )

            messages.info(request, "Leave marked. Family has been notified.")
            return redirect("dashboard:caretaker_dashboard")

    expected_start_str = assignment.application.work_start_time.strftime("%I:%M %p") if assignment.application and assignment.application.work_start_time else "09:00 AM"
    expected_end_str = assignment.application.work_end_time.strftime("%I:%M %p") if assignment.application and assignment.application.work_end_time else "05:00 PM"

    context = {
        "assignment": assignment,
        "attendance": attendance,
        "today": today,
        "expected_start": expected_start_str,
        "expected_end": expected_end_str,
    }
    return render(request, "assignments/mark_attendance.html", context)


@login_required
def view_attendance(request, assignment_id):
    """View attendance records (Family)"""
    if request.user.role != "family":
        messages.error(request, "Access denied.")
        return redirect("users:index")

    assignment = get_object_or_404(
        CareAssignment, id=assignment_id, family=request.user
    )

    # Get month filter
    month = request.GET.get("month")
    year = request.GET.get("year")
    today = date.today()

    if month and year:
        current_month = int(month)
        current_year = int(year)
        start_date = date(current_year, current_month, 1)
        if current_month == 12:
            end_date = date(current_year + 1, 1, 1) - timedelta(days=1)
        else:
            end_date = date(current_year, current_month + 1, 1) - timedelta(days=1)

        attendances = assignment.attendance_records.filter(
            date__gte=start_date, date__lte=end_date
        ).order_by("date")
        month_name = start_date.strftime("%B %Y")
    else:
        # Current month
        current_month = today.month
        current_year = today.year
        start_date = today.replace(day=1)
        end_date = today
        attendances = assignment.attendance_records.filter(
            date__gte=start_date
        ).order_by("date")
        month_name = today.strftime("%B %Y")

    # Calculate previous month
    if current_month == 1:
        prev_month = 12
        prev_year = current_year - 1
    else:
        prev_month = current_month - 1
        prev_year = current_year

    # Calculate next month
    if current_month == 12:
        next_month = 1
        next_year = current_year + 1
    else:
        next_month = current_month + 1
        next_year = current_year

    # Summary - FIXED: Count late by late_minutes, not status
    total_days = attendances.count()
    present = attendances.filter(status="present").count()
    absent = attendances.filter(status="absent").count()
    late = attendances.filter(
        late_minutes__gt=0
    ).count()  # ← FIXED: Count any attendance with late minutes
    leave = attendances.filter(status="leave").count()
    total_overtime = (
        attendances.aggregate(Sum("overtime_hours"))["overtime_hours__sum"] or 0
    )

    # Add day name and late flag to each attendance for template
    for att in attendances:
        att.day_name = att.date.strftime("%A")
        att.is_late = att.late_minutes > 0  # Add this for template

    context = {
        "assignment": assignment,
        "attendances": attendances,
        "month_name": month_name,
        "current_year": current_year,
        "current_month": current_month,
        "prev_year": prev_year,
        "prev_month": prev_month,
        "next_year": next_year,
        "next_month": next_month,
        "summary": {
            "total_days": total_days,
            "present": present,
            "absent": absent,
            "late": late,  # Now correctly counts days with late minutes
            "leave": leave,
            "attendance_percentage": (
                (present / total_days * 100) if total_days > 0 else 0
            ),
            "total_overtime": total_overtime,
        },
    }
    return render(request, "assignments/view_attendance.html", context)


@login_required
def attendance_calendar(request, assignment_id):
    """View attendance calendar view"""
    assignment = get_object_or_404(CareAssignment, id=assignment_id)

    # Check permission
    if request.user != assignment.family and request.user != assignment.caretaker:
        messages.error(request, "Access denied.")
        return redirect("users:index")

    year = int(request.GET.get("year", date.today().year))
    month = int(request.GET.get("month", date.today().month))

    # Get first day of month and number of days
    first_day = date(year, month, 1)
    if month == 12:
        last_day = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        last_day = date(year, month + 1, 1) - timedelta(days=1)

    attendances = {
        att.date: att
        for att in assignment.attendance_records.filter(
            date__gte=first_day, date__lte=last_day
        )
    }

    # Build calendar
    calendar_data = []
    current_date = first_day
    while current_date <= last_day:
        week = []
        for _ in range(7):
            attendance = attendances.get(current_date)
            week.append(
                {
                    "date": current_date,
                    "attendance": attendance,
                    "is_today": current_date == date.today(),
                }
            )
            current_date += timedelta(days=1)
            if current_date > last_day:
                break
        calendar_data.append(week)

    context = {
        "assignment": assignment,
        "calendar_data": calendar_data,
        "year": year,
        "month": month,
        "month_name": first_day.strftime("%B %Y"),
        "prev_month": first_day - timedelta(days=1),
        "next_month": last_day + timedelta(days=1),
    }
    return render(request, "assignments/attendance_calendar.html", context)


# ============================================================================
# SALARY MANAGEMENT
# ============================================================================


@login_required
def manage_salary(request, assignment_id):
    """Manage salary payments (Family)"""
    if request.user.role != "family":
        messages.error(request, "Access denied.")
        return redirect("users:index")

    assignment = get_object_or_404(
        CareAssignment, id=assignment_id, family=request.user
    )

    # Get existing payments
    payments = assignment.salary_payments.all().order_by("-payment_month")

    # Calculate current month salary
    current_month = date.today().replace(day=1)
    attendance_summary = assignment.get_current_attendance_summary()

    if assignment.monthly_salary:
        current_salary = assignment.monthly_salary
        current_payable = (current_salary / 30) * attendance_summary["present_days"]
    else:
        current_salary = assignment.hourly_rate * assignment.work_hours_per_day * 30
        current_payable = (
            assignment.hourly_rate
            * assignment.work_hours_per_day
            * attendance_summary["present_days"]
        )

    # Calculate overtime for current month
    current_month_overtime = (
        assignment.attendance_records.filter(
            date__gte=current_month, status="present"
        ).aggregate(Sum("overtime_hours"))["overtime_hours__sum"]
        or 0
    )

    overtime_pay = current_month_overtime * (assignment.hourly_rate * Decimal("1.5"))

    context = {
        "assignment": assignment,
        "payments": payments,
        "current_month": current_month,
        "current_month_name": current_month.strftime("%B %Y"),
        "current_salary": current_salary,
        "current_payable": current_payable,
        "current_overtime": current_month_overtime,
        "overtime_pay": overtime_pay,
        "attendance_summary": attendance_summary,
    }
    return render(request, "assignments/manage_salary.html", context)


@login_required
def process_salary(request, assignment_id):
    """Process salary payment (Family)"""
    if request.user.role != "family":
        messages.error(request, "Access denied.")
        return redirect("users:index")

    assignment = get_object_or_404(
        CareAssignment, id=assignment_id, family=request.user
    )

    payment_month = request.POST.get("payment_month")

    if payment_month:
        # Calculate attendance for that month
        year, month = map(int, payment_month.split("-"))
        start_date = date(year, month, 1)

        if month == 12:
            end_date = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            end_date = date(year, month + 1, 1) - timedelta(days=1)

        attendances = assignment.attendance_records.filter(
            date__gte=start_date, date__lte=end_date
        )

        days_present = attendances.filter(status="present").count()
        days_absent = attendances.filter(status="absent").count()
        days_late = attendances.filter(status="late").count()
        days_leave = attendances.filter(status="leave").count()
        total_overtime = (
            attendances.aggregate(Sum("overtime_hours"))["overtime_hours__sum"] or 0
        )

        # Calculate salary
        if assignment.monthly_salary:
            base_salary = assignment.monthly_salary
            total_amount = (base_salary / 30) * days_present
        else:
            base_salary = assignment.hourly_rate * assignment.work_hours_per_day * 30
            total_amount = (
                assignment.hourly_rate * assignment.work_hours_per_day * days_present
            )

        # Calculate overtime (1.5x rate)
        overtime_pay = total_overtime * (assignment.hourly_rate * Decimal("1.5"))

        # Create payment record
        payment = SalaryPayment.objects.create(
            assignment=assignment,
            payment_month=start_date,
            base_salary=base_salary,
            overtime_pay=overtime_pay,
            total_amount=total_amount + overtime_pay,
            days_worked=(end_date - start_date).days + 1,
            days_present=days_present,
            days_absent=days_absent,
            days_late=days_late,
            days_leave=days_leave,
            overtime_hours=total_overtime,
            status="pending",
            processed_by=request.user,
        )

        messages.success(
            request,
            f"Salary record created for {payment_month}. Amount: ₹{payment.total_amount:,.2f}",
        )

    return redirect("assignments:manage_salary", assignment_id=assignment.id)


@login_required
def mark_salary_paid(request, payment_id):
    """Mark salary as paid (Family)"""
    payment = get_object_or_404(SalaryPayment, id=payment_id)

    if request.user != payment.assignment.family:
        messages.error(request, "Access denied.")
        return redirect("users:index")

    if request.method == "POST":
        payment.status = "paid"
        payment.payment_date = timezone.now()
        payment.payment_method = request.POST.get("payment_method")
        payment.transaction_id = request.POST.get("transaction_id", "")
        payment.notes = request.POST.get("notes", "")
        payment.save()

        messages.success(
            request,
            f"Salary for {payment.payment_month.strftime('%B %Y')} marked as paid.",
        )

    return redirect("assignments:manage_salary", assignment_id=payment.assignment.id)


@login_required
def salary_history(request, assignment_id):
    """View salary payment history"""
    assignment = get_object_or_404(CareAssignment, id=assignment_id)

    # Check permission
    if request.user != assignment.family and request.user != assignment.caretaker:
        messages.error(request, "Access denied.")
        return redirect("users:index")

    payments = assignment.salary_payments.all().order_by("-payment_month")

    # Calculate total earnings
    total_earned = (
        payments.filter(status="paid").aggregate(Sum("total_amount"))[
            "total_amount__sum"
        ]
        or 0
    )

    context = {
        "assignment": assignment,
        "payments": payments,
        "total_earned": total_earned,
    }
    return render(request, "assignments/salary_history.html", context)


# ============================================================================
# API / JSON ENDPOINTS
# ============================================================================


@login_required
def get_tasks_api(request, assignment_id):
    """API endpoint to get tasks for assignment"""
    assignment = get_object_or_404(CareAssignment, id=assignment_id)

    if request.user != assignment.family and request.user != assignment.caretaker:
        return JsonResponse({"error": "Access denied"}, status=403)

    tasks = assignment.tasks.all().values(
        "id", "title", "status", "priority", "due_date"
    )

    return JsonResponse({"tasks": list(tasks)})


@login_required
def get_attendance_api(request, assignment_id):
    """API endpoint to get attendance for assignment"""
    assignment = get_object_or_404(CareAssignment, id=assignment_id)

    if request.user != assignment.family and request.user != assignment.caretaker:
        return JsonResponse({"error": "Access denied"}, status=403)

    month = request.GET.get("month", date.today().month)
    year = request.GET.get("year", date.today().year)

    start_date = date(int(year), int(month), 1)
    if int(month) == 12:
        end_date = date(int(year) + 1, 1, 1) - timedelta(days=1)
    else:
        end_date = date(int(year), int(month) + 1, 1) - timedelta(days=1)

    attendances = assignment.attendance_records.filter(
        date__gte=start_date, date__lte=end_date
    ).values("date", "status", "actual_hours_worked", "overtime_hours")

    return JsonResponse({"attendances": list(attendances)})
