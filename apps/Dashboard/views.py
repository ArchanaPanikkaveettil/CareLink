from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from apps.Applications.models import CareApplication
from apps.Requests.models import CareRequest

@login_required
def dashboard(request):
    return render(request, "dashboard/dashboard.html")

@login_required
def caretaker_dashboard(request):
    if request.user.role != "caretaker":
        return redirect("index")

    total_applications = CareApplication.objects.filter(
        caretaker=request.user
    ).count()

    pending_applications = CareApplication.objects.filter(
        caretaker=request.user,
        status="pending"
    ).count()

    accepted_applications = CareApplication.objects.filter(
        caretaker=request.user,
        status="accepted"
    ).count()
    
    rejected_applications = CareApplication.objects.filter(
        caretaker=request.user,
        status="rejected"
    ).count()
    
    # Get recent applications
    recent_applications = CareApplication.objects.filter(
        caretaker=request.user
    ).select_related('request').order_by('-applied_at')[:5]

    return render(request, "dashboard/caretaker_dashboard.html", {
        "total_applications": total_applications,
        "pending_applications": pending_applications,
        "accepted_applications": accepted_applications,
        "rejected_applications": rejected_applications,
        "recent_applications": recent_applications
    })

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
    
    # Application statistics
    total_applications = CareApplication.objects.filter(
        request__family=request.user
    ).count()
    
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
    
    # Get recent applications
    recent_applications = CareApplication.objects.filter(
        request__family=request.user
    ).select_related('request', 'caretaker').order_by('-applied_at')[:5]

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
    }

    return render(request, "dashboard/family_dashboard.html", context)