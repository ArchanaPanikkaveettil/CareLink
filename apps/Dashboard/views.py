from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from datetime import date, timedelta
from apps.Applications.models import CareApplication
from apps.Requests.models import CareRequest
from apps.assignments.models import CareAssignment, CareTask, Attendance
from apps.assignments.views import check_missed_tasks
from apps.Notifications.models import Notification

@login_required
def dashboard(request):
    return render(request, "dashboard/dashboard.html")


@login_required
def caretaker_dashboard(request):
    """Dashboard for caretakers/nurses"""
    if request.user.role != 'caretaker':
        messages.error(request, "Access denied.")
        return redirect('users:index')
    
    today = date.today()
    
    # Get applications
    total_applications = CareApplication.objects.filter(caretaker=request.user).count()
    pending_applications = CareApplication.objects.filter(
        caretaker=request.user, 
        status='pending'
    ).count()
    
    # Get assignments
    active_assignments = CareAssignment.objects.filter(
        caretaker=request.user,
        status='active'
    )
    assigned_jobs = active_assignments.count()
    
    # Get today's tasks
    today_tasks = CareTask.objects.filter(
        assignment__caretaker=request.user,
        due_date__date=today,
        status__in=['pending', 'in_progress']
    ).select_related('assignment')
    
    # Get upcoming tasks (next 7 days)
    upcoming_tasks = CareTask.objects.filter(
        assignment__caretaker=request.user,
        due_date__date__gte=today,
        due_date__date__lte=today + timedelta(days=7),
        status__in=['pending', 'in_progress']
    ).select_related('assignment').order_by('due_date')[:5]
    
    # Get completed tasks for today
    completed_tasks_today = CareTask.objects.filter(
        assignment__caretaker=request.user,
        due_date__date=today,
        status='completed'
    ).count()
    
    # Get overdue tasks
    overdue_tasks = CareTask.objects.filter(
        assignment__caretaker=request.user,
        due_date__date__lt=today,
        status__in=['pending', 'in_progress']
    ).count()
    
    # Get today's attendance if any active assignment
    today_attendance = None
    today_assignment = None
    if active_assignments.exists():
        today_assignment = active_assignments.first()
        today_attendance = Attendance.objects.filter(
            assignment=today_assignment,
            date=today
        ).first()
        
        # Trigger missed task check for this assignment
        check_missed_tasks(request, today_assignment.id)
    
    # Get unread notifications count
    unread_notifications = Notification.objects.filter(
        recipient=request.user,
        is_read=False
    ).count()
    
    context = {
        'total_applications': total_applications,
        'pending_applications': pending_applications,
        'assigned_jobs': assigned_jobs,
        'today_tasks': today_tasks,
        'today_tasks_count': today_tasks.count(),
        'upcoming_tasks': upcoming_tasks,
        'completed_tasks_today': completed_tasks_today,
        'overdue_tasks': overdue_tasks,
        'today_attendance': today_attendance,
        'today_assignment': today_assignment,
        'unread_notifications': unread_notifications,
        'is_verified': request.user.is_verified,
        'profile': getattr(request.user, 'caretaker_profile', None),
    }
    
    return render(request, 'dashboard/caretaker_dashboard.html', context)



@login_required
def family_dashboard(request):
    if request.user.role != "family":
        return redirect("index")
    
    # Get statistics for family dashboard
    total_requests = CareRequest.objects.filter(family=request.user).count()
    
    # Request counts by status
    open_requests = CareRequest.objects.filter(
        family=request.user, 
        status="open"
    ).count()
    
    assigned_requests = CareRequest.objects.filter(
        family=request.user,
        status="assigned"
    ).count()
    
    closed_requests = CareRequest.objects.filter(
        family=request.user,
        status="closed"
    ).count()
    
    # Application statistics (excluding withdrawn)
    total_applications = CareApplication.objects.filter(
        request__family=request.user
    ).exclude(status="withdrawn").count()
    
    pending_applications = CareApplication.objects.filter(
        request__family=request.user,
        status="pending"
    ).count()
    
    accepted_applications = CareApplication.objects.filter(
        request__family=request.user,
        status="accepted"
    ).count()
    
    rejected_applications = CareApplication.objects.filter(
        request__family=request.user,
        status="rejected"
    ).count()
    
    # Get recent requests
    recent_requests = CareRequest.objects.filter(
        family=request.user
    ).order_by('-created_at')[:5]

    # Trigger missed task checks for all active assignments
    active_assignments = CareAssignment.objects.filter(family=request.user, status='active')
    for assignment in active_assignments:
        check_missed_tasks(request, assignment.id)
    
    # Get recent applications (excluding withdrawn)
    recent_applications = CareApplication.objects.filter(
        request__family=request.user
    ).exclude(status="withdrawn").select_related('request', 'caretaker').order_by('-applied_at')[:5]

    context = {
        # Request statistics
        "total_requests": total_requests,
        "open_requests": open_requests,
        "assigned_requests": assigned_requests,
        "closed_requests": closed_requests,
        
        # Application statistics
        "total_applications": total_applications,
        "pending_applications": pending_applications,
        "accepted_applications": accepted_applications,
        "rejected_applications": rejected_applications,
        
        # ADD THIS: Pending applications count for the sidebar badge
        "pending_applications_count": pending_applications,
        
        # Recent items
        "recent_requests": recent_requests,
        "recent_applications": recent_applications,
        
        # Profile completion
        "profile": getattr(request.user, 'family_profile', None),
    }

    return render(request, "dashboard/family_dashboard.html", context)