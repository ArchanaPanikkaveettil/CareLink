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
    CareAssignment, DailyCareReport, CareTask, 
    CareNote, Attendance, SalaryPayment
)
from apps.Users.models import User
from apps.Requests.models import CareRequest
from apps.Applications.models import CareApplication


# ==================== ASSIGNMENT MANAGEMENT ====================

@login_required
def create_assignment(request, application_id):
    """Create a care assignment from an accepted application"""
    if request.user.role != 'family':
        messages.error(request, "Access denied. Only families can create assignments.")
        return redirect('users:index')
    
    application = get_object_or_404(CareApplication, id=application_id, status='accepted')
    
    # Check if assignment already exists
    existing = CareAssignment.objects.filter(application=application).first()
    if existing:
        messages.info(request, "An assignment already exists for this application.")
        return redirect('assignments:family_assignment_detail', assignment_id=existing.id)
    
    if request.method == 'POST':
        try:
            # Calculate monthly salary if hourly rate provided
            hourly_rate = Decimal(request.POST.get('hourly_rate', 0))
            work_hours = Decimal(request.POST.get('work_hours_per_day', 8))
            monthly_salary = hourly_rate * work_hours * 30
            
            assignment = CareAssignment.objects.create(
                family=request.user,
                caretaker=application.caretaker.user,
                care_request=application.request,
                application=application,
                assigned_date=timezone.now(),
                start_date=request.POST.get('start_date'),
                shift_type=request.POST.get('shift_type', 'full_time'),
                work_hours_per_day=work_hours,
                hourly_rate=hourly_rate,
                monthly_salary=monthly_salary if hourly_rate > 0 else None,
                notes=request.POST.get('notes', ''),
                status='active'
            )
            
            messages.success(
                request, 
                f"Assignment created successfully! {application.caretaker.user.get_full_name()} is now assigned to you."
            )
            return redirect('assignments:family_assignment_detail', assignment_id=assignment.id)
            
        except Exception as e:
            messages.error(request, f"Error creating assignment: {str(e)}")
    
    context = {
        'application': application,
        'shift_choices': CareAssignment.SHIFT_CHOICES,
    }
    return render(request, 'assignments/create_assignment.html', context)


@login_required
def family_assignments(request):
    """List all assignments for a family"""
    if request.user.role != 'family':
        messages.error(request, "Access denied.")
        return redirect('users:index')
    
    assignments = CareAssignment.objects.filter(
        family=request.user
    ).select_related('caretaker').prefetch_related('attendance_records')
    
    # Filter by status
    status_filter = request.GET.get('status', '')
    if status_filter:
        assignments = assignments.filter(status=status_filter)
    
    # Search
    search_query = request.GET.get('q', '')
    if search_query:
        assignments = assignments.filter(
            Q(caretaker__first_name__icontains=search_query) |
            Q(caretaker__last_name__icontains=search_query) |
            Q(caretaker__email__icontains=search_query)
        )
    
    # Pagination
    paginator = Paginator(assignments, 10)
    page = request.GET.get('page', 1)
    assignments = paginator.get_page(page)
    
    # Add summary for each assignment
    today = date.today()
    for assignment in assignments:
        assignment.today_attendance = assignment.attendance_records.filter(date=today).first()
        assignment.pending_tasks_count = assignment.tasks.filter(
            status__in=['pending', 'in_progress']
        ).count()
        assignment.unread_notes_count = assignment.care_notes.filter(
            read_by_family=False
        ).count()
        assignment.unread_reports_count = assignment.daily_reports.filter(
            family_read=False
        ).count()
    
    context = {
        'assignments': assignments,
        'status_filter': status_filter,
        'search_query': search_query,
    }
    return render(request, 'assignments/family_assignments.html', context)


@login_required
def caretaker_assignments(request):
    """List all assignments for a caretaker"""
    if request.user.role != 'caretaker':
        messages.error(request, "Access denied.")
        return redirect('users:index')
    
    assignments = CareAssignment.objects.filter(
        caretaker=request.user
    ).select_related('family')
    
    # Add today's status
    today = date.today()
    for assignment in assignments:
        assignment.today_attendance = assignment.attendance_records.filter(date=today).first()
        assignment.today_tasks_count = assignment.tasks.filter(
            due_date__date=today,
            status__in=['pending', 'in_progress']
        ).count()
        assignment.pending_tasks_count = assignment.tasks.filter(
            status__in=['pending', 'in_progress']
        ).count()
        assignment.unread_notes_count = assignment.care_notes.filter(
            read_by_caretaker=False
        ).count()
    
    context = {
        'assignments': assignments,
    }
    return render(request, 'assignments/caretaker_assignments.html', context)


@login_required
def family_assignment_detail(request, assignment_id):
    """Detailed view of an assignment for family"""
    if request.user.role != 'family':
        messages.error(request, "Access denied.")
        return redirect('users:index')
    
    assignment = get_object_or_404(
        CareAssignment.objects.select_related('caretaker', 'caretaker__caretaker_profile'),
        id=assignment_id, 
        family=request.user
    )
    
    # Get recent data
    recent_reports = assignment.daily_reports.all()[:7]
    pending_tasks = assignment.tasks.filter(status__in=['pending', 'in_progress'])[:10]
    recent_notes = assignment.care_notes.all()[:10]
    
    # Get attendance for current month
    attendance_summary = assignment.get_current_attendance_summary()
    
    # Get this week's attendance
    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    week_attendance = assignment.attendance_records.filter(
        date__gte=week_start,
        date__lte=today
    ).order_by('date')
    
    context = {
        'assignment': assignment,
        'recent_reports': recent_reports,
        'pending_tasks': pending_tasks,
        'recent_notes': recent_notes,
        'attendance_summary': attendance_summary,
        'week_attendance': week_attendance,
    }
    return render(request, 'assignments/family_assignment_detail.html', context)


@login_required
def caretaker_assignment_detail(request, assignment_id):
    """Detailed view of an assignment for caretaker"""
    if request.user.role != 'caretaker':
        messages.error(request, "Access denied.")
        return redirect('users:index')
    
    assignment = get_object_or_404(
        CareAssignment.objects.select_related('family'),
        id=assignment_id, 
        caretaker=request.user
    )
    
    # Check-in/out for today
    today = date.today()
    today_attendance = Attendance.objects.filter(assignment=assignment, date=today).first()
    
    # Tasks for today
    today_tasks = assignment.tasks.filter(
        due_date__date=today,
        status__in=['pending', 'in_progress']
    )
    
    # Check if report already submitted today
    today_report = assignment.daily_reports.filter(report_date=today).first()
    
    context = {
        'assignment': assignment,
        'today_attendance': today_attendance,
        'today_tasks': today_tasks,
        'today_report': today_report,
    }
    return render(request, 'assignments/caretaker_assignment_detail.html', context)


@login_required
def terminate_assignment(request, assignment_id):
    """Terminate an assignment (Family)"""
    if request.user.role != 'family':
        messages.error(request, "Access denied.")
        return redirect('users:index')
    
    assignment = get_object_or_404(CareAssignment, id=assignment_id, family=request.user)
    
    if request.method == 'POST':
        assignment.status = 'terminated'
        assignment.termination_reason = request.POST.get('reason', '')
        assignment.termination_date = date.today()
        assignment.end_date = date.today()
        assignment.save()
        
        messages.success(request, f"Assignment with {assignment.caretaker.get_full_name()} has been terminated.")
        return redirect('assignments:family_assignments')
    
    context = {
        'assignment': assignment,
    }
    return render(request, 'assignments/terminate_assignment.html', context)


# ==================== DAILY CARE REPORTS ====================

@login_required
def create_daily_report(request, assignment_id):
    """Create daily care report (Caretaker)"""
    if request.user.role != 'caretaker':
        messages.error(request, "Access denied.")
        return redirect('users:index')
    
    assignment = get_object_or_404(
        CareAssignment, 
        id=assignment_id, 
        caretaker=request.user,
        status='active'
    )
    
    # Check if report already exists for today
    today = date.today()
    existing_report = assignment.daily_reports.filter(report_date=today).first()
    
    if request.method == 'POST':
        try:
            if existing_report:
                report = existing_report
            else:
                report = DailyCareReport(assignment=assignment, report_date=today)
            
            # Vital Signs
            report.blood_pressure_systolic = request.POST.get('blood_pressure_systolic') or None
            report.blood_pressure_diastolic = request.POST.get('blood_pressure_diastolic') or None
            report.heart_rate = request.POST.get('heart_rate') or None
            report.temperature = request.POST.get('temperature') or None
            report.blood_sugar = request.POST.get('blood_sugar') or None
            report.oxygen_saturation = request.POST.get('oxygen_saturation') or None
            report.weight = request.POST.get('weight') or None
            
            # Activities
            report.meals_taken = request.POST.get('meals_taken', '')
            report.water_intake = request.POST.get('water_intake', '')
            report.sleep_hours = request.POST.get('sleep_hours') or None
            report.sleep_quality = request.POST.get('sleep_quality', '')
            report.mood = request.POST.get('mood', '')
            
            # Care activities
            report.medications_given = request.POST.get('medications_given', '')
            report.exercises_done = request.POST.get('exercises_done', '')
            report.activities_done = request.POST.get('activities_done', '')
            
            # Observations
            report.observations = request.POST.get('observations', '')
            report.concerns = request.POST.get('concerns', '')
            report.recommendations = request.POST.get('recommendations', '')
            
            # Photo
            if 'photo' in request.FILES:
                report.photo = request.FILES['photo']
            
            report.save()
            
            messages.success(request, "Daily care report submitted successfully!")
            return redirect('assignments:caretaker_assignment_detail', assignment_id=assignment.id)
            
        except Exception as e:
            messages.error(request, f"Error submitting report: {str(e)}")
    
    context = {
        'assignment': assignment,
        'report': existing_report,
        'mood_choices': DailyCareReport.MOOD_CHOICES,
        'sleep_quality_choices': DailyCareReport._meta.get_field('sleep_quality').choices,
    }
    return render(request, 'assignments/create_daily_report.html', context)


@login_required
def view_reports(request, assignment_id):
    """View all daily reports (Family)"""
    if request.user.role != 'family':
        messages.error(request, "Access denied.")
        return redirect('users:index')
    
    assignment = get_object_or_404(
        CareAssignment, 
        id=assignment_id, 
        family=request.user
    )
    
    # Mark reports as read
    unread_reports = assignment.daily_reports.filter(family_read=False)
    for report in unread_reports:
        report.family_read = True
        report.read_at = timezone.now()
        report.save()
    
    # Filter by date range
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    reports = assignment.daily_reports.all()
    
    if start_date:
        reports = reports.filter(report_date__gte=start_date)
    if end_date:
        reports = reports.filter(report_date__lte=end_date)
    
    # Statistics
    stats = reports.aggregate(
        avg_heart_rate=Avg('heart_rate'),
        avg_sleep=Avg('sleep_hours'),
        total_reports=Count('id'),
        reports_with_concerns=Count('id', filter=Q(concerns__isnull=False) & ~Q(concerns=''))
    )
    
    context = {
        'assignment': assignment,
        'reports': reports,
        'stats': stats,
    }
    return render(request, 'assignments/view_reports.html', context)


@login_required
def report_detail(request, report_id):
    """View single report detail"""
    report = get_object_or_404(DailyCareReport, id=report_id)
    
    # Check permission
    if request.user != report.assignment.family and request.user != report.assignment.caretaker:
        messages.error(request, "Access denied.")
        return redirect('users:index')
    
    # Mark as read if family
    if request.user.role == 'family' and not report.family_read:
        report.family_read = True
        report.read_at = timezone.now()
        report.save()
    
    context = {
        'report': report,
    }
    return render(request, 'assignments/report_detail.html', context)


@login_required
def add_family_notes(request, report_id):
    """Add family notes to a report"""
    report = get_object_or_404(DailyCareReport, id=report_id, assignment__family=request.user)
    
    if request.method == 'POST':
        report.family_notes = request.POST.get('family_notes', '')
        report.save()
        messages.success(request, "Notes added successfully!")
        return redirect('assignments:report_detail', report_id=report.id)
    
    return redirect('assignments:report_detail', report_id=report.id)


# ==================== TASKS MANAGEMENT ====================

@login_required
def create_task(request, assignment_id):
    """Create task for caretaker (Family)"""
    if request.user.role != 'family':
        messages.error(request, "Access denied.")
        return redirect('users:index')
    
    assignment = get_object_or_404(
        CareAssignment, 
        id=assignment_id, 
        family=request.user,
        status='active'
    )
    
    if request.method == 'POST':
        try:
            due_date = request.POST.get('due_date')
            if due_date:
                due_date = datetime.strptime(due_date, '%Y-%m-%dT%H:%M')
            else:
                due_date = timezone.now() + timedelta(days=1)
            
            task = CareTask.objects.create(
                assignment=assignment,
                title=request.POST.get('title'),
                description=request.POST.get('description'),
                priority=request.POST.get('priority', 'medium'),
                due_date=due_date,
                assigned_by=request.user
            )
            
            messages.success(request, f"Task '{task.title}' created successfully!")
            return redirect('assignments:family_assignment_detail', assignment_id=assignment.id)
            
        except Exception as e:
            messages.error(request, f"Error creating task: {str(e)}")
    
    context = {
        'assignment': assignment,
        'priority_choices': CareTask.PRIORITY_CHOICES,
    }
    return render(request, 'assignments/create_task.html', context)


@login_required
def update_task_status(request, task_id):
    """Update task status (Caretaker)"""
    task = get_object_or_404(CareTask, id=task_id)
    
    if request.user != task.assignment.caretaker:
        messages.error(request, "Access denied.")
        return redirect('users:index')
    
    if request.method == 'POST':
        status = request.POST.get('status')
        notes = request.POST.get('notes', '')
        
        task.status = status
        task.caretaker_notes = notes
        
        if status == 'completed':
            task.completed_at = timezone.now()
        
        task.save()
        
        messages.success(request, f"Task '{task.title}' marked as {status}.")
    
    return redirect('assignments:caretaker_assignment_detail', assignment_id=task.assignment.id)


@login_required
def task_list(request, assignment_id):
    """List all tasks for an assignment"""
    assignment = get_object_or_404(CareAssignment, id=assignment_id)
    
    # Check permission
    if request.user != assignment.family and request.user != assignment.caretaker:
        messages.error(request, "Access denied.")
        return redirect('users:index')
    
    tasks = assignment.tasks.all()
    
    # Filter by status
    status_filter = request.GET.get('status', '')
    if status_filter:
        tasks = tasks.filter(status=status_filter)
    
    context = {
        'assignment': assignment,
        'tasks': tasks,
        'status_filter': status_filter,
    }
    return render(request, 'assignments/task_list.html', context)


@login_required
def task_detail(request, task_id):
    """View task details"""
    task = get_object_or_404(CareTask, id=task_id)
    
    # Check permission
    if request.user != task.assignment.family and request.user != task.assignment.caretaker:
        messages.error(request, "Access denied.")
        return redirect('users:index')
    
    if request.method == 'POST' and request.user == task.assignment.family:
        task.family_feedback = request.POST.get('feedback', '')
        task.save()
        messages.success(request, "Feedback added!")
    
    context = {
        'task': task,
    }
    return render(request, 'assignments/task_detail.html', context)


# ==================== NOTES MANAGEMENT ====================

@login_required
def create_note(request, assignment_id):
    """Create professional note (Both Family and Caretaker)"""
    assignment = get_object_or_404(CareAssignment, id=assignment_id)
    
    # Check permission
    if request.user != assignment.family and request.user != assignment.caretaker:
        messages.error(request, "Access denied.")
        return redirect('users:index')
    
    if request.method == 'POST':
        try:
            note = CareNote.objects.create(
                assignment=assignment,
                title=request.POST.get('title'),
                content=request.POST.get('content'),
                note_type=request.POST.get('note_type', 'general'),
                created_by=request.user,
                is_important=request.POST.get('is_important') == 'on',
                is_urgent=request.POST.get('is_urgent') == 'on'
            )
            
            messages.success(request, "Note added successfully!")
            
            if request.user.role == 'family':
                return redirect('assignments:family_assignment_detail', assignment_id=assignment.id)
            else:
                return redirect('assignments:caretaker_assignment_detail', assignment_id=assignment.id)
                
        except Exception as e:
            messages.error(request, f"Error creating note: {str(e)}")
    
    context = {
        'assignment': assignment,
        'note_types': CareNote.NOTE_TYPES,
    }
    return render(request, 'assignments/create_note.html', context)


@login_required
def note_list(request, assignment_id):
    """List all notes for an assignment"""
    assignment = get_object_or_404(CareAssignment, id=assignment_id)
    
    # Check permission
    if request.user != assignment.family and request.user != assignment.caretaker:
        messages.error(request, "Access denied.")
        return redirect('users:index')
    
    notes = assignment.care_notes.all()
    
    # Mark as read
    if request.user.role == 'family':
        notes.filter(read_by_family=False).update(read_by_family=True, read_at=timezone.now())
    else:
        notes.filter(read_by_caretaker=False).update(read_by_caretaker=True, read_at=timezone.now())
    
    context = {
        'assignment': assignment,
        'notes': notes,
    }
    return render(request, 'assignments/note_list.html', context)


@login_required
def note_detail(request, note_id):
    """View note details"""
    note = get_object_or_404(CareNote, id=note_id)
    
    # Check permission
    if request.user != note.assignment.family and request.user != note.assignment.caretaker:
        messages.error(request, "Access denied.")
        return redirect('users:index')
    
    # Mark as read
    if request.user.role == 'family' and not note.read_by_family:
        note.read_by_family = True
        note.read_at = timezone.now()
        note.save()
    elif request.user.role == 'caretaker' and not note.read_by_caretaker:
        note.read_by_caretaker = True
        note.read_at = timezone.now()
        note.save()
    
    context = {
        'note': note,
    }
    return render(request, 'assignments/note_detail.html', context)


# ==================== ATTENDANCE MANAGEMENT ====================

@login_required
def mark_attendance(request, assignment_id):
    """Mark attendance (Caretaker)"""
    if request.user.role != 'caretaker':
        messages.error(request, "Access denied.")
        return redirect('users:index')
    
    assignment = get_object_or_404(
        CareAssignment, 
        id=assignment_id, 
        caretaker=request.user,
        status='active'
    )
    
    today = date.today()
    attendance, created = Attendance.objects.get_or_create(
        assignment=assignment,
        date=today,
        defaults={'status': 'present'}
    )
    
    if request.method == 'POST':
        action = request.POST.get('action')
        current_time = datetime.now().time()
        
        if action == 'check_in':
            if not attendance.check_in_time:
                attendance.check_in_time = current_time
                attendance.status = 'present'
                attendance.check_in_location = request.POST.get('location', '')
                messages.success(request, f"Checked in at {current_time.strftime('%I:%M %p')}")
            else:
                messages.warning(request, "Already checked in today!")
                
        elif action == 'check_out':
            if attendance.check_in_time and not attendance.check_out_time:
                attendance.check_out_time = current_time
                attendance.check_out_location = request.POST.get('location', '')
                attendance.calculate_work_hours()
                messages.success(request, f"Checked out at {current_time.strftime('%I:%M %p')}")
                messages.info(request, f"Hours worked today: {attendance.actual_hours_worked:.2f} hours")
                if attendance.overtime_hours > 0:
                    messages.info(request, f"Overtime: {attendance.overtime_hours:.2f} hours")
            else:
                messages.warning(request, "Check-in first or already checked out!")
                
        elif action == 'mark_absent':
            attendance.status = 'absent'
            attendance.notes = request.POST.get('notes', '')
            messages.info(request, "Marked as absent")
            
        elif action == 'mark_leave':
            attendance.status = 'leave'
            attendance.notes = request.POST.get('notes', '')
            messages.info(request, "Leave marked")
        
        attendance.save()
        return redirect('assignments:caretaker_assignment_detail', assignment_id=assignment.id)
    
    context = {
        'assignment': assignment,
        'attendance': attendance,
        'today': today,
    }
    return render(request, 'assignments/mark_attendance.html', context)


@login_required
def view_attendance(request, assignment_id):
    """View attendance records (Family)"""
    if request.user.role != 'family':
        messages.error(request, "Access denied.")
        return redirect('users:index')
    
    assignment = get_object_or_404(
        CareAssignment, 
        id=assignment_id, 
        family=request.user
    )
    
    # Get month filter
    month = request.GET.get('month')
    year = request.GET.get('year')
    today = date.today()
    
    if month and year:
        start_date = date(int(year), int(month), 1)
        if int(month) == 12:
            end_date = date(int(year)+1, 1, 1) - timedelta(days=1)
        else:
            end_date = date(int(year), int(month)+1, 1) - timedelta(days=1)
        
        attendances = assignment.attendance_records.filter(
            date__gte=start_date,
            date__lte=end_date
        ).order_by('date')
        month_name = start_date.strftime('%B %Y')
    else:
        # Current month
        start_date = today.replace(day=1)
        end_date = today
        attendances = assignment.attendance_records.filter(date__gte=start_date).order_by('date')
        month_name = today.strftime('%B %Y')
    
    # Summary
    total_days = attendances.count()
    present = attendances.filter(status='present').count()
    absent = attendances.filter(status='absent').count()
    late = attendances.filter(status='late').count()
    leave = attendances.filter(status='leave').count()
    total_overtime = attendances.aggregate(Sum('overtime_hours'))['overtime_hours__sum'] or 0
    
    context = {
        'assignment': assignment,
        'attendances': attendances,
        'month_name': month_name,
        'summary': {
            'total_days': total_days,
            'present': present,
            'absent': absent,
            'late': late,
            'leave': leave,
            'attendance_percentage': (present / total_days * 100) if total_days > 0 else 0,
            'total_overtime': total_overtime
        }
    }
    return render(request, 'assignments/view_attendance.html', context)


@login_required
def attendance_calendar(request, assignment_id):
    """View attendance calendar view"""
    assignment = get_object_or_404(CareAssignment, id=assignment_id)
    
    # Check permission
    if request.user != assignment.family and request.user != assignment.caretaker:
        messages.error(request, "Access denied.")
        return redirect('users:index')
    
    year = int(request.GET.get('year', date.today().year))
    month = int(request.GET.get('month', date.today().month))
    
    # Get first day of month and number of days
    first_day = date(year, month, 1)
    if month == 12:
        last_day = date(year+1, 1, 1) - timedelta(days=1)
    else:
        last_day = date(year, month+1, 1) - timedelta(days=1)
    
    attendances = {
        att.date: att for att in assignment.attendance_records.filter(
            date__gte=first_day,
            date__lte=last_day
        )
    }
    
    # Build calendar
    calendar_data = []
    current_date = first_day
    while current_date <= last_day:
        week = []
        for _ in range(7):
            attendance = attendances.get(current_date)
            week.append({
                'date': current_date,
                'attendance': attendance,
                'is_today': current_date == date.today()
            })
            current_date += timedelta(days=1)
            if current_date > last_day:
                break
        calendar_data.append(week)
    
    context = {
        'assignment': assignment,
        'calendar_data': calendar_data,
        'year': year,
        'month': month,
        'month_name': first_day.strftime('%B %Y'),
        'prev_month': first_day - timedelta(days=1),
        'next_month': last_day + timedelta(days=1),
    }
    return render(request, 'assignments/attendance_calendar.html', context)


# ==================== SALARY MANAGEMENT ====================

@login_required
def manage_salary(request, assignment_id):
    """Manage salary payments (Family)"""
    if request.user.role != 'family':
        messages.error(request, "Access denied.")
        return redirect('users:index')
    
    assignment = get_object_or_404(
        CareAssignment, 
        id=assignment_id, 
        family=request.user
    )
    
    # Get existing payments
    payments = assignment.salary_payments.all().order_by('-payment_month')
    
    # Calculate current month salary
    current_month = date.today().replace(day=1)
    attendance_summary = assignment.get_current_attendance_summary()
    
    if assignment.monthly_salary:
        current_salary = assignment.monthly_salary
        current_payable = (current_salary / 30) * attendance_summary['present_days']
    else:
        current_salary = assignment.hourly_rate * assignment.work_hours_per_day * 30
        current_payable = assignment.hourly_rate * assignment.work_hours_per_day * attendance_summary['present_days']
    
    # Calculate overtime for current month
    current_month_overtime = assignment.attendance_records.filter(
        date__gte=current_month,
        status='present'
    ).aggregate(Sum('overtime_hours'))['overtime_hours__sum'] or 0
    
    overtime_pay = current_month_overtime * (assignment.hourly_rate * Decimal('1.5'))
    
    context = {
        'assignment': assignment,
        'payments': payments,
        'current_month': current_month,
        'current_month_name': current_month.strftime('%B %Y'),
        'current_salary': current_salary,
        'current_payable': current_payable,
        'current_overtime': current_month_overtime,
        'overtime_pay': overtime_pay,
        'attendance_summary': attendance_summary,
    }
    return render(request, 'assignments/manage_salary.html', context)


@login_required
def process_salary(request, assignment_id):
    """Process salary payment (Family)"""
    if request.user.role != 'family':
        messages.error(request, "Access denied.")
        return redirect('users:index')
    
    assignment = get_object_or_404(
        CareAssignment, 
        id=assignment_id, 
        family=request.user
    )
    
    payment_month = request.POST.get('payment_month')
    
    if payment_month:
        # Calculate attendance for that month
        year, month = map(int, payment_month.split('-'))
        start_date = date(year, month, 1)
        
        if month == 12:
            end_date = date(year+1, 1, 1) - timedelta(days=1)
        else:
            end_date = date(year, month+1, 1) - timedelta(days=1)
        
        attendances = assignment.attendance_records.filter(
            date__gte=start_date,
            date__lte=end_date
        )
        
        days_present = attendances.filter(status='present').count()
        days_absent = attendances.filter(status='absent').count()
        days_late = attendances.filter(status='late').count()
        days_leave = attendances.filter(status='leave').count()
        total_overtime = attendances.aggregate(Sum('overtime_hours'))['overtime_hours__sum'] or 0
        
        # Calculate salary
        if assignment.monthly_salary:
            base_salary = assignment.monthly_salary
            total_amount = (base_salary / 30) * days_present
        else:
            base_salary = assignment.hourly_rate * assignment.work_hours_per_day * 30
            total_amount = assignment.hourly_rate * assignment.work_hours_per_day * days_present
        
        # Calculate overtime (1.5x rate)
        overtime_pay = total_overtime * (assignment.hourly_rate * Decimal('1.5'))
        
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
            status='pending',
            processed_by=request.user
        )
        
        messages.success(request, f"Salary record created for {payment_month}. Amount: ₹{payment.total_amount:,.2f}")
    
    return redirect('assignments:manage_salary', assignment_id=assignment.id)


@login_required
def mark_salary_paid(request, payment_id):
    """Mark salary as paid (Family)"""
    payment = get_object_or_404(SalaryPayment, id=payment_id)
    
    if request.user != payment.assignment.family:
        messages.error(request, "Access denied.")
        return redirect('users:index')
    
    if request.method == 'POST':
        payment.status = 'paid'
        payment.payment_date = timezone.now()
        payment.payment_method = request.POST.get('payment_method')
        payment.transaction_id = request.POST.get('transaction_id', '')
        payment.notes = request.POST.get('notes', '')
        payment.save()
        
        messages.success(request, f"Salary for {payment.payment_month.strftime('%B %Y')} marked as paid.")
    
    return redirect('assignments:manage_salary', assignment_id=payment.assignment.id)


@login_required
def salary_history(request, assignment_id):
    """View salary payment history"""
    assignment = get_object_or_404(CareAssignment, id=assignment_id)
    
    # Check permission
    if request.user != assignment.family and request.user != assignment.caretaker:
        messages.error(request, "Access denied.")
        return redirect('users:index')
    
    payments = assignment.salary_payments.all().order_by('-payment_month')
    
    # Calculate total earnings
    total_earned = payments.filter(status='paid').aggregate(Sum('total_amount'))['total_amount__sum'] or 0
    
    context = {
        'assignment': assignment,
        'payments': payments,
        'total_earned': total_earned,
    }
    return render(request, 'assignments/salary_history.html', context)


# ==================== API/JSON VIEWS ====================

@login_required
def get_tasks_api(request, assignment_id):
    """API endpoint to get tasks for assignment"""
    assignment = get_object_or_404(CareAssignment, id=assignment_id)
    
    if request.user != assignment.family and request.user != assignment.caretaker:
        return JsonResponse({'error': 'Access denied'}, status=403)
    
    tasks = assignment.tasks.all().values(
        'id', 'title', 'status', 'priority', 'due_date'
    )
    
    return JsonResponse({'tasks': list(tasks)})


@login_required
def get_attendance_api(request, assignment_id):
    """API endpoint to get attendance for assignment"""
    assignment = get_object_or_404(CareAssignment, id=assignment_id)
    
    if request.user != assignment.family and request.user != assignment.caretaker:
        return JsonResponse({'error': 'Access denied'}, status=403)
    
    month = request.GET.get('month', date.today().month)
    year = request.GET.get('year', date.today().year)
    
    start_date = date(int(year), int(month), 1)
    if int(month) == 12:
        end_date = date(int(year)+1, 1, 1) - timedelta(days=1)
    else:
        end_date = date(int(year), int(month)+1, 1) - timedelta(days=1)
    
    attendances = assignment.attendance_records.filter(
        date__gte=start_date,
        date__lte=end_date
    ).values('date', 'status', 'actual_hours_worked', 'overtime_hours')
    
    return JsonResponse({'attendances': list(attendances)})