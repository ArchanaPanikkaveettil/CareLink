from datetime import timedelta
import json

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.db.models import Q, Count
from django.utils import timezone
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.contrib.auth import update_session_auth_hash
from django.http import HttpResponse, JsonResponse

from CareLink import settings
from .forms import AdminUserEditForm
from apps.Users.admin_utils import AdminEmailService, AdminExporter
from .models import (
    User,
    CaretakerProfile,
    FamilyProfile,
    CaretakerAvailability,
    ElderProfile,
)

# Import from other apps with try/except for safety
try:
    from apps.Requests.models import CareRequest
except ImportError:
    CareRequest = None

try:
    from apps.Applications.models import CareApplication
except ImportError:
    CareApplication = None

# Get User model once
User = get_user_model()


# -------------------------------------------------------------------------
# Home / Landing Page
# -------------------------------------------------------------------------
def index(request):
    """Home / Landing Page"""
    return render(request, "users/index.html")


# --------------------
# logout
# ----------------------
def custom_logout(request):
    logout(request)
    return redirect("users:index")


# -------------------------------------------------------------------------
# Caretaker Registration
# -------------------------------------------------------------------------
def caretaker_register(request):
    if request.method == "POST":
        try:
            # ========== ACCOUNT DETAILS ==========
            username = request.POST.get("username")
            email = request.POST.get("email")
            first_name = request.POST.get("first_name")
            last_name = request.POST.get("last_name")
            password = request.POST.get("password")
            confirm_password = request.POST.get("confirm_password")
            phone = request.POST.get("phone")

            if not all(
                [
                    username,
                    email,
                    first_name,
                    last_name,
                    password,
                    confirm_password,
                    phone,
                ]
            ):
                messages.error(request, "All account fields are required.")
                return redirect("users:caretaker_register")

            if password != confirm_password:
                messages.error(request, "Passwords do not match.")
                return redirect("users:caretaker_register")

            if len(password) < 6:
                messages.error(request, "Password must be at least 6 characters.")
                return redirect("users:caretaker_register")

            if (
                User.objects.filter(username=username).exists()
                or User.objects.filter(email=email).exists()
            ):
                messages.error(request, "Username or email already exists.")
                return redirect("users:caretaker_register")

            # ========== VERIFICATION FIELDS ==========
            date_of_birth = request.POST.get("date_of_birth")
            gender = request.POST.get("gender")
            certificate = request.FILES.get("certificate")
            identity_proof = request.FILES.get("identity_proof")
            resume = request.FILES.get("resume")
            background_check = request.FILES.get("background_check")
            qualification = request.POST.get("qualification")
            experience_years = request.POST.get("experience_years")
            address = request.POST.get("address")
            city = request.POST.get("city")
            state = request.POST.get("state")
            pincode = request.POST.get("pincode")
            emergency_name = request.POST.get("emergency_name")
            emergency_phone = request.POST.get("emergency_phone")
            emergency_relation = request.POST.get("emergency_relation")

            if not all(
                [
                    date_of_birth,
                    gender,
                    certificate,
                    identity_proof,
                    qualification,
                    experience_years,
                    address,
                    city,
                    state,
                    pincode,
                    emergency_name,
                    emergency_phone,
                    emergency_relation,
                ]
            ):
                messages.error(
                    request,
                    "All verification fields are required for security purposes.",
                )
                return redirect("users:caretaker_register")

            accepted_terms = request.POST.get("accepted_terms") == "on"
            if not accepted_terms:
                messages.error(request, "You must accept the Terms and Conditions.")
                return redirect("users:caretaker_register")

            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                role="caretaker",
                is_verified=False,
                verification_status="pending",
                phone=phone,
                accepted_terms=accepted_terms,
                accepted_terms_date=timezone.now(),
            )

            profile = CaretakerProfile.objects.create(
                user=user,
                emergency_contact_name=emergency_name,
                emergency_contact_phone=emergency_phone,
                emergency_contact_relation=emergency_relation,
                date_of_birth=date_of_birth,
                gender=gender,
                experience_years=experience_years,
                qualification=qualification,
                certificate=certificate,
                identity_proof=identity_proof,
                resume=resume,
                background_check=background_check,
                address=address,
                city=city,
                state=state,
                pincode=pincode,
                country="India",
                skills="",
                languages="",
                bio="",
                availability_status="available",
                verified_by_admin=False,
            )

            messages.success(
                request,
                "Registration successful! Your documents are under verification.",
            )
            return redirect("users:login")

        except Exception as e:
            messages.error(request, f"Registration failed: {str(e)}")
            return redirect("users:caretaker_register")

    return render(request, "users/caretaker_register.html")


# -------------------------------------------------------------------------
# Family Registration
# -------------------------------------------------------------------------
def family_register(request):
    if request.method == "POST":
        try:
            first_name = request.POST.get("first_name")
            last_name = request.POST.get("last_name")
            email = request.POST.get("email")
            password = request.POST.get("password")
            confirm_password = request.POST.get("confirm_password")
            phone = request.POST.get("phone")

            if not all(
                [first_name, last_name, email, password, confirm_password, phone]
            ):
                messages.error(request, "All fields are required.")
                return redirect("users:family_register")

            if password != confirm_password:
                messages.error(request, "Passwords do not match.")
                return redirect("users:family_register")

            if len(password) < 6:
                messages.error(request, "Password must be at least 6 characters long.")
                return redirect("users:family_register")

            if User.objects.filter(username=email).exists():
                messages.error(request, "Email already registered.")
                return redirect("users:family_register")

            accepted_terms = request.POST.get("accepted_terms") == "on"
            if not accepted_terms:
                messages.error(request, "You must accept the Terms and Conditions.")
                return redirect("users:family_register")

            user = User.objects.create_user(
                username=email,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                role="family",
                is_verified=True,
                phone=phone,
                accepted_terms=accepted_terms,
                accepted_terms_date=timezone.now(),
            )

            FamilyProfile.objects.create(
                user=user,
                phone=phone,
                address="",
            )

            messages.success(request, "Registration successful! You can now login.")
            return redirect("users:login")

        except Exception as e:
            messages.error(request, f"Registration failed: {str(e)}")
            return redirect("users:family_register")

    return render(request, "users/family_register.html")


# -------------------------------------------------------------------------
# Custom Login
# -------------------------------------------------------------------------
def custom_login(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        remember_me = request.POST.get("remember")
        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)

            # Set session expiration based on remember me
            if remember_me:
                # Session expires after 30 days (in seconds)
                request.session.set_expiry(30 * 24 * 60 * 60)
            else:
                # Session expires when browser closes
                request.session.set_expiry(0)

            if user.is_superuser or user.is_staff:
                return redirect("users:admin_dashboard")

            if user.role == "family":
                return redirect("dashboard:family_dashboard")
            elif user.role == "caretaker":
                try:
                    if (
                        hasattr(user, "caretaker_profile")
                        and user.caretaker_profile.verified_by_admin
                    ):
                        return redirect("dashboard:caretaker_dashboard")
                    else:
                        return redirect("users:verification_pending")
                except:
                    return redirect("users:verification_pending")
            else:
                return redirect("users:index")
        else:
            return render(
                request, "users/login.html", {"error": "Invalid email or password"}
            )

    return render(request, "users/login.html")


# -------------------------------------------------------------------------
# ADMIN PANEL VIEWS
# -------------------------------------------------------------------------
@login_required
def admin_dashboard(request):
    """Custom admin dashboard for superusers and staff"""
    if not (request.user.is_superuser or request.user.is_staff):
        messages.error(request, "Access denied. Admin privileges required.")
        return redirect("users:index")

    total_users = User.objects.count()
    total_caretakers = User.objects.filter(role="caretaker").count()
    total_families = User.objects.filter(role="family").count()
    pending_verifications = User.objects.filter(
        role="caretaker", verification_status="pending"
    ).count()
    recent_users = User.objects.order_by("-date_joined")[:10]
    pending_caretakers = CaretakerProfile.objects.filter(
        user__verification_status="pending"
    ).select_related("user")[:10]

    # Get notifications for admin
    from apps.Notifications.models import Notification

    notifications = Notification.objects.filter(recipient=request.user).order_by(
        "-created_at"
    )[:10]
    unread_notifications_count = Notification.objects.filter(
        recipient=request.user, is_read=False
    ).count()

    context = {
        "total_users": total_users,
        "total_caretakers": total_caretakers,
        "total_families": total_families,
        "pending_verifications": pending_verifications,
        "pending_verifications_count": pending_verifications,
        "recent_users": recent_users,
        "pending_caretakers": pending_caretakers,
        "notifications": notifications,
        "unread_notifications_count": unread_notifications_count,
    }
    return render(request, "admin/admin_dashboard.html", context)


@login_required
def admin_users_list(request):
    """List all users with filters"""
    if not (request.user.is_superuser or request.user.is_staff):
        messages.error(request, "Access denied.")
        return redirect("users:index")

    role_filter = request.GET.get("role", "")
    status_filter = request.GET.get("status", "")
    search_query = request.GET.get("q", "")

    users = User.objects.all().order_by("-date_joined")

    if role_filter:
        users = users.filter(role=role_filter)

    if status_filter:
        if status_filter == "verified":
            users = users.filter(is_verified=True)
        elif status_filter == "pending":
            users = users.filter(verification_status="pending")
        elif status_filter == "rejected":
            users = users.filter(verification_status="rejected")
        elif status_filter == "active":
            users = users.filter(is_active=True)
        elif status_filter == "inactive":
            users = users.filter(is_active=False)

    if search_query:
        users = users.filter(
            Q(username__icontains=search_query)
            | Q(email__icontains=search_query)
            | Q(first_name__icontains=search_query)
            | Q(last_name__icontains=search_query)
        )

    page = request.GET.get("page", 1)
    paginator = Paginator(users, 20)

    try:
        users = paginator.page(page)
    except PageNotAnInteger:
        users = paginator.page(1)
    except EmptyPage:
        users = paginator.page(paginator.num_pages)

    context = {
        "users": users,
        "role_filter": role_filter,
        "status_filter": status_filter,
        "search_query": search_query,
        "total_users": paginator.count,
    }
    return render(request, "admin/admin_users_list.html", context)


@login_required
def admin_caretakers_list(request):
    """List all caretakers"""
    if not (request.user.is_superuser or request.user.is_staff):
        messages.error(request, "Access denied.")
        return redirect("users:index")

    search_query = request.GET.get("q", "")
    status_filter = request.GET.get("status", "")

    caretakers = (
        CaretakerProfile.objects.select_related("user")
        .all()
        .order_by("-user__date_joined")
    )

    if search_query:
        caretakers = caretakers.filter(
            Q(user__first_name__icontains=search_query)
            | Q(user__last_name__icontains=search_query)
            | Q(user__email__icontains=search_query)
            | Q(city__icontains=search_query)
            | Q(qualification__icontains=search_query)
        )

    if status_filter:
        if status_filter == "verified":
            caretakers = caretakers.filter(user__is_verified=True)
        elif status_filter == "pending":
            caretakers = caretakers.filter(user__verification_status="pending")
        elif status_filter == "rejected":
            caretakers = caretakers.filter(user__verification_status="rejected")
        elif status_filter == "active":
            caretakers = caretakers.filter(user__is_active=True)
        elif status_filter == "inactive":
            caretakers = caretakers.filter(user__is_active=False)

    page = request.GET.get("page", 1)
    paginator = Paginator(caretakers, 15)

    try:
        caretakers = paginator.page(page)
    except PageNotAnInteger:
        caretakers = paginator.page(1)
    except EmptyPage:
        caretakers = paginator.page(paginator.num_pages)

    context = {
        "caretakers": caretakers,
        "search_query": search_query,
        "status_filter": status_filter,
    }
    return render(request, "admin/admin_caretakers_list.html", context)


@login_required
def admin_families_list(request):
    """List all families"""
    if not (request.user.is_superuser or request.user.is_staff):
        messages.error(request, "Access denied.")
        return redirect("users:index")

    search_query = request.GET.get("q", "")
    status_filter = request.GET.get("status", "")

    families = (
        FamilyProfile.objects.select_related("user")
        .all()
        .order_by("-user__date_joined")
    )

    if search_query:
        families = families.filter(
            Q(user__first_name__icontains=search_query)
            | Q(user__last_name__icontains=search_query)
            | Q(user__email__icontains=search_query)
            | Q(city__icontains=search_query)
        )

    if status_filter:
        if status_filter == "active":
            families = families.filter(user__is_active=True)
        elif status_filter == "inactive":
            families = families.filter(user__is_active=False)

    page = request.GET.get("page", 1)
    paginator = Paginator(families, 15)

    try:
        families = paginator.page(page)
    except PageNotAnInteger:
        families = paginator.page(1)
    except EmptyPage:
        families = paginator.page(paginator.num_pages)

    context = {
        "families": families,
        "search_query": search_query,
        "status_filter": status_filter,
    }
    return render(request, "admin/admin_families_list.html", context)


@login_required
def admin_verifications(request):
    """List all pending verifications"""
    if not (request.user.is_superuser or request.user.is_staff):
        messages.error(request, "Access denied.")
        return redirect("users:index")

    pending_caretakers = (
        CaretakerProfile.objects.filter(user__verification_status="pending")
        .select_related("user")
        .order_by("user__date_joined")
    )

    page = request.GET.get("page", 1)
    paginator = Paginator(pending_caretakers, 15)

    try:
        pending_caretakers = paginator.page(page)
    except PageNotAnInteger:
        pending_caretakers = paginator.page(1)
    except EmptyPage:
        pending_caretakers = paginator.page(paginator.num_pages)

    context = {
        "pending_caretakers": pending_caretakers,
    }
    return render(request, "admin/admin_verifications.html", context)


@login_required
def admin_verify_caretaker(request, id):
    """Verify caretaker documents"""
    if not (request.user.is_superuser or request.user.is_staff):
        messages.error(request, "Access denied.")
        return redirect("users:index")

    caretaker = get_object_or_404(CaretakerProfile, id=id)

    if request.method == "POST":
        action = request.POST.get("action")
        remarks = request.POST.get("remarks", "")

        if action == "approve":
            caretaker.user.verification_status = "verified"
            caretaker.user.is_verified = True
            caretaker.verified_by_admin = True
            caretaker.verified_date = timezone.now()
            caretaker.verification_remarks = remarks
            messages.success(
                request,
                f"Caretaker {caretaker.user.get_full_name()} has been verified.",
            )

        elif action == "reject":
            caretaker.user.verification_status = "rejected"
            caretaker.user.is_verified = False
            caretaker.verified_by_admin = False
            caretaker.verification_remarks = remarks
            messages.warning(
                request,
                f"Caretaker {caretaker.user.get_full_name()} has been rejected.",
            )

        caretaker.user.save()
        caretaker.save()
        return redirect("users:admin_verifications")

    documents = {
        "certificate": caretaker.certificate.url if caretaker.certificate else None,
        "identity_proof": (
            caretaker.identity_proof.url if caretaker.identity_proof else None
        ),
        "resume": caretaker.resume.url if caretaker.resume else None,
        "background_check": (
            caretaker.background_check.url if caretaker.background_check else None
        ),
    }

    context = {
        "caretaker": caretaker,
        "documents": documents,
    }
    return render(request, "admin/admin_verify_caretaker.html", context)


@login_required
def admin_user_detail(request, id):
    """View user details"""
    if not (request.user.is_superuser or request.user.is_staff):
        messages.error(request, "Access denied.")
        return redirect("users:index")

    user = get_object_or_404(User, id=id)

    profile = None
    if user.role == "caretaker":
        try:
            profile = user.caretaker_profile
        except CaretakerProfile.DoesNotExist:
            profile = None
    elif user.role == "family":
        try:
            profile = user.family_profile
        except FamilyProfile.DoesNotExist:
            profile = None

    context = {
        "viewed_user": user,
        "profile": profile,
    }
    return render(request, "admin/admin_user_detail.html", context)


@login_required
def admin_requests(request):
    """View all care requests"""
    if not (request.user.is_superuser or request.user.is_staff):
        messages.error(request, "Access denied.")
        return redirect("users:index")

    search_query = request.GET.get("q", "")
    status_filter = request.GET.get("status", "")

    if CareRequest is None:
        context = {
            "requests": [],
            "total_requests": 0,
            "open_requests": 0,
            "assigned_requests": 0,
            "completed_requests": 0,
        }
        return render(request, "admin/admin_requests.html", context)

    requests = (
        CareRequest.objects.select_related("family").all().order_by("-created_at")
    )

    if search_query:
        requests = requests.filter(
            Q(title__icontains=search_query)
            | Q(description__icontains=search_query)
            | Q(family__first_name__icontains=search_query)
            | Q(family__last_name__icontains=search_query)
        )

    if status_filter:
        requests = requests.filter(status=status_filter)

    total_requests = CareRequest.objects.count()
    open_requests = CareRequest.objects.filter(status="open").count()
    assigned_requests = CareRequest.objects.filter(status="assigned").count()
    completed_requests = CareRequest.objects.filter(status="closed").count()

    # Count applications for each request - FIXED: use 'request' not 'care_request'
    if CareApplication:
        for req in requests:
            # The field in CareApplication is 'request', not 'care_request'
            req.applications_count = CareApplication.objects.filter(request=req).count()
    else:
        for req in requests:
            req.applications_count = 0

    page = request.GET.get("page", 1)
    paginator = Paginator(requests, 15)

    try:
        requests = paginator.page(page)
    except PageNotAnInteger:
        requests = paginator.page(1)
    except EmptyPage:
        requests = paginator.page(paginator.num_pages)

    context = {
        "requests": requests,
        "search_query": search_query,
        "status_filter": status_filter,
        "total_requests": total_requests,
        "open_requests": open_requests,
        "assigned_requests": assigned_requests,
        "completed_requests": completed_requests,
    }

    return render(request, "admin/admin_requests.html", context)


@login_required
def admin_request_detail(request, request_id):
    """View care request details"""
    if not (request.user.is_superuser or request.user.is_staff):
        messages.error(request, "Access denied.")
        return redirect("users:index")

    if CareRequest is None:
        messages.error(request, "CareRequest model not found.")
        return redirect("users:admin_requests")

    care_request = get_object_or_404(CareRequest, id=request_id)
    applications = []
    if CareApplication:
        # FIXED: use 'request' not 'care_request'
        applications = CareApplication.objects.filter(
            request=care_request
        ).select_related("caretaker__user")

    context = {
        "request": care_request,
        "applications": applications,
    }
    return render(request, "admin/admin_request_detail.html", context)


@login_required
def admin_applications(request):
    """View all applications"""
    if not (request.user.is_superuser or request.user.is_staff):
        messages.error(request, "Access denied.")
        return redirect("users:index")

    search_query = request.GET.get("q", "")
    status_filter = request.GET.get("status", "")

    if CareApplication is None:
        context = {
            "applications": [],
            "total_applications": 0,
            "pending_applications": 0,
            "accepted_applications": 0,
            "rejected_applications": 0,
        }
        return render(request, "admin/admin_applications.html", context)

    # FIXED: Use correct select_related paths
    # CareApplication has:
    # - caretaker (ForeignKey to CaretakerProfile)
    # - request (ForeignKey to CareRequest, which has family)
    applications = (
        CareApplication.objects.select_related(
            "caretaker",  # This gets CaretakerProfile
            "request",  # This gets CareRequest
            "request__family",  # This gets the family User through the request
        )
        .all()
        .order_by("-applied_at")
    )

    if search_query:
        applications = applications.filter(
            Q(caretaker__user__first_name__icontains=search_query)
            | Q(caretaker__user__last_name__icontains=search_query)
            | Q(request__family__first_name__icontains=search_query)
            | Q(request__family__last_name__icontains=search_query)
        )

    if status_filter:
        applications = applications.filter(status=status_filter)

    total_applications = CareApplication.objects.count()
    pending_applications = CareApplication.objects.filter(status="pending").count()
    accepted_applications = CareApplication.objects.filter(status="accepted").count()
    rejected_applications = CareApplication.objects.filter(status="rejected").count()

    page = request.GET.get("page", 1)
    paginator = Paginator(applications, 15)

    try:
        applications = paginator.page(page)
    except PageNotAnInteger:
        applications = paginator.page(1)
    except EmptyPage:
        applications = paginator.page(paginator.num_pages)

    context = {
        "applications": applications,
        "search_query": search_query,
        "status_filter": status_filter,
        "total_applications": total_applications,
        "pending_applications": pending_applications,
        "accepted_applications": accepted_applications,
        "rejected_applications": rejected_applications,
    }

    return render(request, "admin/admin_applications.html", context)


@login_required
def admin_application_detail(request, app_id):
    """View application details"""
    if not (request.user.is_superuser or request.user.is_staff):
        messages.error(request, "Access denied.")
        return redirect("users:index")

    if CareApplication is None:
        messages.error(request, "CareApplication model not found.")
        return redirect("users:admin_applications")

    application = get_object_or_404(CareApplication, id=app_id)

    context = {
        "application": application,
    }
    return render(request, "admin/admin_application_detail.html", context)


@login_required
def admin_reports(request):
    """Generate and view reports"""
    if not (request.user.is_superuser or request.user.is_staff):
        messages.error(request, "Access denied.")
        return redirect("users:index")

    start_date = request.GET.get("start_date")
    end_date = request.GET.get("end_date")
    report_type = request.GET.get("type", "users")

    total_users = User.objects.filter(is_active=True).count()
    total_caretakers = User.objects.filter(role="caretaker", is_active=True).count()
    total_families = User.objects.filter(role="family", is_active=True).count()
    verified_caretakers = User.objects.filter(
        role="caretaker", is_verified=True
    ).count()
    pending_verifications = User.objects.filter(
        role="caretaker", verification_status="pending"
    ).count()
    active_caretakers = CaretakerProfile.objects.filter(
        availability_status="available"
    ).count()
    active_families = User.objects.filter(role="family", is_active=True).count()

    monthly_requests = 0
    if CareRequest:
        today = timezone.now()
        month_start = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        monthly_requests = CareRequest.objects.filter(
            created_at__gte=month_start
        ).count()

    context = {
        "report_type": report_type,
        "start_date": start_date,
        "end_date": end_date,
        "total_users": total_users,
        "total_caretakers": total_caretakers,
        "total_families": total_families,
        "verified_caretakers": verified_caretakers,
        "pending_verifications": pending_verifications,
        "active_caretakers": active_caretakers,
        "active_families": active_families,
        "monthly_requests": monthly_requests,
        "user_growth": 12,
        "caretaker_growth": 8,
        "family_growth": 15,
        "verified_growth": 8,
        "pending_growth": 5,
        "request_growth": 25,
    }

    return render(request, "admin/admin_reports.html", context)


@login_required
def admin_audit_logs(request):
    """View system audit logs"""
    if not request.user.is_superuser:
        messages.error(request, "Access denied. Superuser privileges required.")
        return redirect("users:admin_dashboard")

    user_filter = request.GET.get("user", "")
    action_filter = request.GET.get("action", "")
    from_date = request.GET.get("from_date", "")
    to_date = request.GET.get("to_date", "")

    try:
        from apps.Users.models import AuditLog

        logs = AuditLog.objects.select_related("user").all()

        if user_filter:
            logs = logs.filter(
                Q(user__username__icontains=user_filter)
                | Q(user__email__icontains=user_filter)
            )

        if action_filter:
            logs = logs.filter(action=action_filter)

        if from_date:
            logs = logs.filter(created_at__date__gte=from_date)

        if to_date:
            logs = logs.filter(created_at__date__lte=to_date)

        total_logs = logs.count()
        today = timezone.now().date()
        week_ago = today - timedelta(days=7)

        today_logs = logs.filter(created_at__date=today).count()
        week_logs = logs.filter(created_at__date__gte=week_ago).count()
        failed_attempts = logs.filter(
            status="failed", created_at__date__gte=week_ago
        ).count()
        unique_users = logs.values("user").distinct().count()

        page = request.GET.get("page", 1)
        paginator = Paginator(logs, 20)

        try:
            logs = paginator.page(page)
        except PageNotAnInteger:
            logs = paginator.page(1)
        except EmptyPage:
            logs = paginator.page(paginator.num_pages)

    except (ImportError, NameError):
        logs = []
        total_logs = 0
        today_logs = 0
        week_logs = 0
        failed_attempts = 0
        unique_users = 0

    context = {
        "logs": logs,
        "total_logs": total_logs,
        "today_logs": today_logs,
        "week_logs": week_logs,
        "failed_attempts": failed_attempts,
        "unique_users": unique_users,
        "user_filter": user_filter,
        "action_filter": action_filter,
        "from_date": from_date,
        "to_date": to_date,
    }

    return render(request, "admin/admin_audit_logs.html", context)


@login_required
def admin_audit_logs(request):
    """View system audit logs"""
    if not request.user.is_superuser:
        messages.error(request, "Access denied. Superuser privileges required.")
        return redirect("users:admin_dashboard")

    user_filter = request.GET.get("user", "")
    action_filter = request.GET.get("action", "")
    from_date = request.GET.get("from_date", "")
    to_date = request.GET.get("to_date", "")

    # Try to get audit logs if model exists
    try:
        from apps.Users.models import AuditLog

        logs = AuditLog.objects.select_related("user").all()

        if user_filter:
            logs = logs.filter(
                Q(user__username__icontains=user_filter)
                | Q(user__email__icontains=user_filter)
            )

        if action_filter:
            logs = logs.filter(action=action_filter)

        if from_date:
            logs = logs.filter(created_at__date__gte=from_date)

        if to_date:
            logs = logs.filter(created_at__date__lte=to_date)

        total_logs = logs.count()
        today = timezone.now().date()
        week_ago = today - timedelta(days=7)

        today_logs = logs.filter(created_at__date=today).count()
        week_logs = logs.filter(created_at__date__gte=week_ago).count()
        failed_attempts = logs.filter(
            status="failed", created_at__date__gte=week_ago
        ).count()
        unique_users = logs.values("user").distinct().count()

        page = request.GET.get("page", 1)
        paginator = Paginator(logs, 20)

        try:
            logs = paginator.page(page)
        except PageNotAnInteger:
            logs = paginator.page(1)
        except EmptyPage:
            logs = paginator.page(paginator.num_pages)

    except (ImportError, NameError):
        # Sample data for testing when no AuditLog model exists
        from django.utils import timezone
        from datetime import datetime

        # Create a mock log object for display
        class MockLog:
            def __init__(self, user, action, resource, details, ip, status, created_at):
                self.user = user
                self.action = action
                self.resource = resource
                self.details = details
                self.ip_address = ip
                self.status = status
                self.created_at = created_at

        sample_logs = [
            MockLog(
                request.user,
                "login",
                "Authentication",
                "Successful login",
                "127.0.0.1",
                "success",
                timezone.now(),
            ),
            MockLog(
                request.user,
                "update",
                "User Profile",
                "Updated profile information",
                "127.0.0.1",
                "success",
                timezone.now() - timedelta(hours=2),
            ),
        ]

        logs = sample_logs
        total_logs = len(sample_logs)
        today_logs = 1
        week_logs = 2
        failed_attempts = 0
        unique_users = 1

    context = {
        "logs": logs,
        "total_logs": total_logs,
        "today_logs": today_logs,
        "week_logs": week_logs,
        "failed_attempts": failed_attempts,
        "unique_users": unique_users,
        "user_filter": user_filter,
        "action_filter": action_filter,
        "from_date": from_date,
        "to_date": to_date,
    }

    return render(request, "admin/admin_audit_logs.html", context)


@login_required
def admin_settings(request):
    """Admin system settings"""
    if not (request.user.is_superuser):
        messages.error(request, "Access denied. Superuser privileges required.")
        return redirect("users:admin_dashboard")

    if request.method == "POST":
        messages.success(request, "Settings updated successfully.")
        return redirect("users:admin_settings")

    context = {}
    return render(request, "admin/admin_settings.html")


@login_required
def admin_toggle_user_status(request, id):
    """Enable/disable user account"""
    if not (request.user.is_superuser):
        messages.error(request, "Access denied. Superuser privileges required.")
        return redirect("users:admin_dashboard")

    user = get_object_or_404(User, id=id)

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "enable":
            user.is_active = True
            messages.success(request, f"User {user.get_full_name()} has been enabled.")
        elif action == "disable":
            user.is_active = False
            messages.success(request, f"User {user.get_full_name()} has been disabled.")
        elif action == "make_staff":
            user.is_staff = True
            messages.success(request, f"User {user.get_full_name()} is now staff.")
        elif action == "remove_staff":
            user.is_staff = False
            messages.success(
                request, f"Staff privileges removed from {user.get_full_name()}."
            )

        user.save()

    return redirect("users:admin_user_detail", id=id)


# -------------------------------------------------------------------------
# Admin User Management
# -------------------------------------------------------------------------
@login_required
def admin_user_edit(request, id):
    """Edit user from admin panel"""
    if not (request.user.is_superuser or request.user.is_staff):
        messages.error(request, "Access denied.")
        return redirect("users:admin_dashboard")

    user = get_object_or_404(User, id=id)

    if request.method == "POST":
        form = AdminUserEditForm(request.POST, instance=user)
        if form.is_valid():
            form.save()
            messages.success(
                request, f"User {user.get_full_name()} updated successfully."
            )
            return redirect("users:admin_user_detail", id=user.id)
    else:
        form = AdminUserEditForm(instance=user)

    context = {
        "edit_user": user,
        "form": form,
    }
    return render(request, "admin/admin_user_edit.html", context)


@login_required
def admin_user_delete(request, id):
    """Delete user from admin panel"""
    if not request.user.is_superuser:
        messages.error(request, "Only superusers can delete users.")
        return redirect("users:admin_dashboard")

    user = get_object_or_404(User, id=id)

    if request.method == "POST":
        username = user.get_full_name()
        user.delete()
        messages.success(request, f"User {username} has been deleted.")
        return redirect("users:admin_users_list")

    context = {
        "delete_user": user,
    }
    return render(request, "admin/admin_user_confirm_delete.html", context)


# -------------------------------------------------------------------------
# Admin Password & Sessions
# -------------------------------------------------------------------------


@login_required
def admin_profile(request):
    """Admin profile settings"""
    if not (request.user.is_superuser or request.user.is_staff):
        messages.error(request, "Access denied.")
        return redirect("users:index")

    if request.method == "POST":
        # Update admin profile
        request.user.first_name = request.POST.get(
            "first_name", request.user.first_name
        )
        request.user.last_name = request.POST.get("last_name", request.user.last_name)
        request.user.email = request.POST.get("email", request.user.email)
        request.user.phone = request.POST.get("phone", request.user.phone)

        if "profile_picture" in request.FILES:
            request.user.profile_picture = request.FILES["profile_picture"]

        request.user.save()
        messages.success(request, "Profile updated successfully.")
        return redirect("users:admin_profile")

    context = {
        "admin_user": request.user,
    }
    return render(request, "admin/admin_profile.html", context)


@login_required
def admin_settings(request):
    """Admin system settings"""
    if not request.user.is_superuser:
        messages.error(request, "Access denied. Superuser privileges required.")
        return redirect("users:admin_dashboard")

    if request.method == "POST":
        # Handle settings update
        messages.success(request, "Settings updated successfully.")
        return redirect("users:admin_settings")

    context = {}
    return render(request, "admin/admin_settings.html")


@login_required
def admin_change_password(request):
    """Change admin user password"""
    if not (request.user.is_superuser or request.user.is_staff):
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse(
                {"success": False, "error": "Access denied"}, status=403
            )
        messages.error(request, "Access denied.")
        return redirect("users:index")

    if request.method == "POST":
        current_password = request.POST.get("current_password")
        new_password = request.POST.get("new_password")
        confirm_password = request.POST.get("confirm_password")

        if not all([current_password, new_password, confirm_password]):
            messages.error(request, "All fields are required.")
            return redirect("users:admin_profile")

        if not request.user.check_password(current_password):
            messages.error(request, "Current password is incorrect.")
            return redirect("users:admin_profile")

        if new_password != confirm_password:
            messages.error(request, "New passwords do not match.")
            return redirect("users:admin_profile")

        if len(new_password) < 8:
            messages.error(request, "Password must be at least 8 characters long.")
            return redirect("users:admin_profile")

        if not any(char.isdigit() for char in new_password):
            messages.error(request, "Password must contain at least one number.")
            return redirect("users:admin_profile")

        try:
            request.user.set_password(new_password)
            request.user.save()
            update_session_auth_hash(request, request.user)
            messages.success(request, "Password changed successfully.")
            return redirect("users:admin_profile")
        except Exception as e:
            messages.error(request, f"Error changing password: {str(e)}")
            return redirect("users:admin_profile")

    return redirect("users:admin_profile")


@login_required
def admin_logout_all_sessions(request):
    """Logout all other sessions for the admin user"""
    if not (request.user.is_superuser or request.user.is_staff):
        return JsonResponse({"success": False, "error": "Access denied"}, status=403)

    if request.method == "POST":
        try:
            from django.contrib.sessions.models import Session

            current_session = request.session.session_key
            user_sessions = []
            all_sessions = Session.objects.all()

            for session in all_sessions:
                try:
                    data = session.get_decoded()
                    if data.get("_auth_user_id") == str(request.user.id):
                        if session.session_key != current_session:
                            user_sessions.append(session.session_key)
                except:
                    pass

            for session_key in user_sessions:
                Session.objects.filter(session_key=session_key).delete()

            messages.success(
                request, f"Logged out {len(user_sessions)} other sessions."
            )
            return redirect("users:admin_profile")

        except Exception as e:
            messages.error(request, f"Error logging out sessions: {str(e)}")
            return redirect("users:admin_profile")

    return redirect("users:admin_profile")


@login_required
def admin_change_password(request):
    """Change admin user password"""
    if not (request.user.is_superuser or request.user.is_staff):
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse(
                {"success": False, "error": "Access denied"}, status=403
            )
        messages.error(request, "Access denied.")
        return redirect("users:index")

    if request.method == "POST":
        current_password = request.POST.get("current_password")
        new_password = request.POST.get("new_password")
        confirm_password = request.POST.get("confirm_password")

        if not all([current_password, new_password, confirm_password]):
            messages.error(request, "All fields are required.")
            return redirect("users:admin_profile")

        if not request.user.check_password(current_password):
            messages.error(request, "Current password is incorrect.")
            return redirect("users:admin_profile")

        if new_password != confirm_password:
            messages.error(request, "New passwords do not match.")
            return redirect("users:admin_profile")

        if len(new_password) < 8:
            messages.error(request, "Password must be at least 8 characters long.")
            return redirect("users:admin_profile")

        if not any(char.isdigit() for char in new_password):
            messages.error(request, "Password must contain at least one number.")
            return redirect("users:admin_profile")

        try:
            request.user.set_password(new_password)
            request.user.save()
            update_session_auth_hash(request, request.user)
            messages.success(request, "Password changed successfully.")
            return redirect("users:admin_profile")
        except Exception as e:
            messages.error(request, f"Error changing password: {str(e)}")
            return redirect("users:admin_profile")

    return redirect("users:admin_profile")


@login_required
def admin_logout_all_sessions(request):
    """Logout all other sessions for the admin user"""
    if not (request.user.is_superuser or request.user.is_staff):
        return JsonResponse({"success": False, "error": "Access denied"}, status=403)

    if request.method == "POST":
        try:
            from django.contrib.sessions.models import Session

            current_session = request.session.session_key
            user_sessions = []
            all_sessions = Session.objects.all()

            for session in all_sessions:
                try:
                    data = session.get_decoded()
                    if data.get("_auth_user_id") == str(request.user.id):
                        if session.session_key != current_session:
                            user_sessions.append(session.session_key)
                except:
                    pass

            for session_key in user_sessions:
                Session.objects.filter(session_key=session_key).delete()

            messages.success(
                request, f"Logged out {len(user_sessions)} other sessions."
            )
            return redirect("users:admin_profile")

        except Exception as e:
            messages.error(request, f"Error logging out sessions: {str(e)}")
            return redirect("users:admin_profile")

    return redirect("users:admin_profile")


# -------------------------------------------------------------------------
# Admin AJAX Views
# -------------------------------------------------------------------------
@login_required
def admin_quick_view_caretaker(request, id):
    """Quick view caretaker details via AJAX"""
    if not (request.user.is_superuser or request.user.is_staff):
        return JsonResponse({"error": "Access denied"}, status=403)

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        caretaker = get_object_or_404(CaretakerProfile, id=id)

        data = {
            "full_name": caretaker.user.get_full_name(),
            "email": caretaker.user.email,
            "phone": caretaker.user.phone or "Not provided",
            "dob": (
                str(caretaker.date_of_birth)
                if caretaker.date_of_birth
                else "Not provided"
            ),
            "gender": caretaker.gender or "Not provided",
            "experience": caretaker.experience_years,
            "qualification": caretaker.qualification or "Not provided",
            "skills": caretaker.skills or "Not provided",
            "languages": caretaker.languages or "Not provided",
            "address": caretaker.address or "Not provided",
            "city": caretaker.city or "Not provided",
            "state": caretaker.state or "Not provided",
            "pincode": caretaker.pincode or "Not provided",
        }

        return JsonResponse(data)

    return JsonResponse({"error": "Invalid request"}, status=400)


@login_required
def admin_bulk_verify(request):
    """Bulk verify caretakers"""
    if not (request.user.is_superuser or request.user.is_staff):
        return JsonResponse({"error": "Access denied"}, status=403)

    if request.method == "POST":
        try:
            data = json.loads(request.body)
            caretaker_ids = data.get("caretaker_ids", [])
            action = data.get("action", "approve")
            remarks = data.get("remarks", "")

            caretakers = CaretakerProfile.objects.filter(id__in=caretaker_ids)
            count = 0

            for caretaker in caretakers:
                if action == "approve":
                    caretaker.user.verification_status = "verified"
                    caretaker.user.is_verified = True
                    caretaker.verified_by_admin = True
                    caretaker.verified_date = timezone.now()
                    caretaker.verification_remarks = remarks
                    count += 1
                elif action == "reject":
                    caretaker.user.verification_status = "rejected"
                    caretaker.user.is_verified = False
                    caretaker.verification_remarks = remarks
                    count += 1

                caretaker.user.save()
                caretaker.save()

            return JsonResponse(
                {"success": True, "message": f"{count} caretakers have been {action}d."}
            )

        except Exception as e:
            return JsonResponse({"error": str(e)}, status=400)

    return JsonResponse({"error": "Invalid request"}, status=400)


@login_required
def admin_export_data(request):
    """Export data based on type"""
    if not (request.user.is_superuser or request.user.is_staff):
        messages.error(request, "Access denied.")
        return redirect("users:admin_dashboard")

    export_type = request.GET.get("type", "users")

    if export_type == "users":
        users = User.objects.all().order_by("-date_joined")
        return AdminExporter.export_users_to_csv(users)
    elif export_type == "caretakers":
        caretakers = CaretakerProfile.objects.select_related("user").all()
        return AdminExporter.export_caretakers_to_csv(caretakers)
    elif export_type == "families":
        families = FamilyProfile.objects.select_related("user").all()
        messages.info(request, "Family export coming soon.")
        return redirect("users:admin_reports")

    messages.error(request, "Invalid export type.")
    return redirect("users:admin_reports")


@login_required
def admin_system_health(request):
    """System health check endpoint for admin"""
    if not request.user.is_superuser:
        return JsonResponse({"error": "Access denied"}, status=403)

    from django.db import connection
    from django.core.cache import cache
    import os

    health_data = {
        "status": "healthy",
        "timestamp": timezone.now().isoformat(),
        "checks": {},
    }

    try:
        connection.ensure_connection()
        health_data["checks"]["database"] = {"status": "ok"}
    except Exception as e:
        health_data["checks"]["database"] = {"status": "error", "error": str(e)}
        health_data["status"] = "unhealthy"

    try:
        cache.set("health_check", "ok", 10)
        if cache.get("health_check") == "ok":
            health_data["checks"]["cache"] = {"status": "ok"}
        else:
            health_data["checks"]["cache"] = {"status": "error"}
    except Exception as e:
        health_data["checks"]["cache"] = {"status": "error", "error": str(e)}

    try:
        static_dir = settings.STATIC_ROOT if settings.STATIC_ROOT else "static"
        media_dir = settings.MEDIA_ROOT
        health_data["checks"]["storage"] = {
            "status": "ok",
            "static_exists": os.path.exists(static_dir),
            "media_exists": os.path.exists(media_dir),
        }
    except Exception as e:
        health_data["checks"]["storage"] = {"status": "error", "error": str(e)}

    return JsonResponse(health_data)


@login_required
def admin_clear_old_logs(request):
    """Clear audit logs older than specified days"""
    if not request.user.is_superuser:
        return JsonResponse({"error": "Access denied"}, status=403)

    if request.method == "POST":
        try:
            days = int(request.POST.get("days", 30))
            cutoff_date = timezone.now() - timedelta(days=days)

            from apps.Users.models import AuditLog

            deleted_count = AuditLog.objects.filter(
                created_at__lt=cutoff_date
            ).delete()[0]

            return JsonResponse(
                {
                    "success": True,
                    "message": f"Deleted {deleted_count} logs older than {days} days.",
                }
            )
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=400)

    return JsonResponse({"error": "Invalid request"}, status=400)


# -------------------------------------------------------------------------
# Test View
# -------------------------------------------------------------------------
@login_required
def admin_test(request):
    """Test view to check if admin panel is working"""
    if not (request.user.is_superuser or request.user.is_staff):
        return HttpResponse("Access denied", status=403)

    return HttpResponse(
        f"""
        <h1>Admin Panel Test</h1>
        <p>Welcome {request.user.get_full_name()}!</p>
        <p>Your role: {request.user.role}</p>
        <p>Verification status: {request.user.verification_status}</p>
        <p>Phone: {request.user.phone}</p>
        <p><a href="/admin-panel/dashboard/">Go to Dashboard</a></p>
    """
    )


# -------------------------------------------------------------------------
# User Profile Views (Caretaker & Family)
# -------------------------------------------------------------------------
@login_required
def caretaker_profile(request):
    if request.user.role != "caretaker":
        messages.error(request, "Access denied. This page is for caretakers only.")
        return redirect("users:index")

    try:
        profile = request.user.caretaker_profile
        skills_list = (
            [skill.strip() for skill in profile.skills.split(",") if skill.strip()]
            if profile.skills
            else []
        )
        languages_list = (
            [lang.strip() for lang in profile.languages.split(",") if lang.strip()]
            if profile.languages
            else []
        )
    except CaretakerProfile.DoesNotExist:
        profile = CaretakerProfile.objects.create(user=request.user, address="")
        skills_list = []
        languages_list = []
        messages.info(request, "Please complete your profile information.")

    availability = profile.availability_schedule.all().order_by("day_of_week")

    # Get reviews for this caretaker
    reviews = profile.reviews.all().order_by("-created_at")

    context = {
        "profile": profile,
        "user": request.user,
        "availability": availability,
        "skills_list": skills_list,
        "languages_list": languages_list,
        "reviews": reviews,
    }
    return render(request, "users/caretaker_profile.html", context)


@login_required
def update_caretaker_profile(request):
    """Update caretaker profile with detailed information"""
    if request.user.role != "caretaker":
        messages.error(request, "Access denied.")
        return redirect("users:index")

    try:
        profile = request.user.caretaker_profile
    except CaretakerProfile.DoesNotExist:
        profile = CaretakerProfile.objects.create(user=request.user)

    if request.method == "POST":
        try:
            # Personal Information
            if request.POST.get("date_of_birth"):
                profile.date_of_birth = request.POST.get("date_of_birth")
            profile.gender = request.POST.get("gender", profile.gender)

            # Contact Information
            request.user.phone = request.POST.get("phone", request.user.phone)
            profile.emergency_contact_name = request.POST.get(
                "emergency_contact_name", ""
            )
            profile.emergency_contact_phone = request.POST.get(
                "emergency_contact_phone", ""
            )
            profile.emergency_contact_relation = request.POST.get(
                "emergency_contact_relation", ""
            )

            # Professional Information
            if request.POST.get("experience_years"):
                profile.experience_years = int(request.POST.get("experience_years"))
            profile.experience_level = request.POST.get("experience_level", "entry")
            profile.qualification = request.POST.get("qualification", "")
            profile.specialized_training = request.POST.get("specialized_training", "")

            # Skills
            profile.skills = request.POST.get("skills", "")
            profile.languages = request.POST.get("languages", "")
            profile.employment_type = request.POST.get("employment_type", "full_time")

            # Bio
            profile.bio = request.POST.get("bio", "")
            profile.achievements = request.POST.get("achievements", "")

            # Availability
            profile.availability_status = request.POST.get(
                "availability_status", "available"
            )
            profile.preferred_shift = request.POST.get("preferred_shift", "flexible")
            profile.willing_to_relocate = (
                request.POST.get("willing_to_relocate") == "on"
            )
            if request.POST.get("max_travel_distance"):
                profile.max_travel_distance = int(
                    request.POST.get("max_travel_distance")
                )

            # Location
            profile.address = request.POST.get("address", "")
            profile.city = request.POST.get("city", "")
            profile.state = request.POST.get("state", "")
            profile.country = request.POST.get("country", "India")
            profile.pincode = request.POST.get("pincode", "")

            # Documents
            if "resume" in request.FILES:
                profile.resume = request.FILES["resume"]
            if "background_check" in request.FILES:
                profile.background_check = request.FILES["background_check"]
            if "profile_picture" in request.FILES:
                request.user.profile_picture = request.FILES["profile_picture"]

            profile.save()
            request.user.save()

            messages.success(request, "Profile updated successfully!")
            return redirect("users:caretaker_profile")

        except Exception as e:
            messages.error(request, f"Error updating profile: {str(e)}")

    context = {"profile": profile}

    return render(request, "users/update_caretaker_profile.html", context)


@login_required
def verification_pending(request):
    if request.user.role != "caretaker":
        return redirect("users:index")

    if request.user.is_verified:
        return redirect("dashboard:caretaker_dashboard")

    return render(request, "users/verification_pending.html")


@login_required
def search_caretakers(request):
    if request.user.role != "family":
        messages.error(
            request, "Access denied. Only families can search for caretakers."
        )
        return redirect("users:index")

    caretakers = CaretakerProfile.objects.filter(
        user__role="caretaker", user__is_verified=True
    ).select_related("user")

    query = request.GET.get("q")
    if query:
        caretakers = caretakers.filter(
            Q(user__first_name__icontains=query)
            | Q(user__last_name__icontains=query)
            | Q(qualification__icontains=query)
            | Q(city__icontains=query)
        )

    min_exp = request.GET.get("experience")
    if min_exp and min_exp.isdigit():
        caretakers = caretakers.filter(experience_years__gte=int(min_exp))

    availability = request.GET.get("availability")
    if availability:
        caretakers = caretakers.filter(availability_status=availability)

    return render(request, "users/search_caretakers.html", {"caretakers": caretakers})


@login_required
def caretaker_detail(request, id):
    try:
        caretaker = User.objects.get(id=id, role="caretaker")
    except User.DoesNotExist:
        messages.error(request, f"Caretaker with ID {id} not found.")
        return redirect("users:search_caretakers")

    try:
        profile = CaretakerProfile.objects.get(user=caretaker)
    except CaretakerProfile.DoesNotExist:
        profile = None

    # Get reviews for this caregiver
    from apps.assignments.models import CaregiverReview

    reviews = CaregiverReview.objects.filter(caregiver=caretaker).select_related(
        "family"
    )

    # Calculate average rating
    if reviews.exists():
        total_rating = sum(review.rating for review in reviews)
        average_rating = total_rating / reviews.count()
    else:
        average_rating = 0

    context = {
        "caretaker": caretaker,
        "profile": profile,
        "reviews": reviews,
        "average_rating": average_rating,
    }
    return render(request, "users/caretaker_detail.html", context)


@login_required
def family_profile(request):
    if request.user.role != "family":
        messages.error(request, "Access denied.")
        return redirect("users:index")

    try:
        profile = request.user.family_profile
    except FamilyProfile.DoesNotExist:
        profile = FamilyProfile.objects.create(
            user=request.user,
            phone=request.user.phone or "",
            address="",
            patient_name="",
            patient_age=None,
            primary_medical_condition="",
            care_required="",
        )
        messages.info(request, "Please complete your profile information.")

    user_requests = []
    total_requests = 0
    open_requests = 0
    total_applications = 0

    if CareRequest:
        user_requests = CareRequest.objects.filter(family=request.user)
        total_requests = user_requests.count()
        open_requests = user_requests.filter(status="open").count()

        if CareApplication:
            # FIXED: use 'request' not 'care_request'
            for req in user_requests:
                total_applications += CareApplication.objects.filter(
                    request=req
                ).count()

    context = {
        "profile": profile,
        "user": request.user,
        "total_requests": total_requests,
        "open_requests": open_requests,
        "total_applications": total_applications,
    }
    return render(request, "users/family_profile.html", context)


@login_required
def update_family_profile(request):
    if request.user.role != "family":
        messages.error(request, "Access denied.")
        return redirect("users:index")

    try:
        profile = request.user.family_profile
    except FamilyProfile.DoesNotExist:
        profile = FamilyProfile.objects.create(
            user=request.user, phone=request.user.phone or ""
        )

    if request.method == "POST":
        try:
            # Contact
            profile.phone = request.POST.get("phone", "")
            profile.alternate_phone = request.POST.get("alternate_phone", "")
            profile.emergency_contact_name = request.POST.get(
                "emergency_contact_name", ""
            )
            profile.emergency_contact_phone = request.POST.get(
                "emergency_contact_phone", ""
            )
            profile.emergency_contact_relation = request.POST.get(
                "emergency_contact_relation", ""
            )

            # Address
            profile.address = request.POST.get("address", "")
            profile.city = request.POST.get("city", "")
            profile.state = request.POST.get("state", "")
            profile.country = request.POST.get("country", "India")
            profile.pincode = request.POST.get("pincode", "")
            profile.landmark = request.POST.get("landmark", "")
            profile.residence_type = request.POST.get("residence_type", "apartment")

            # Family
            profile.family_type = request.POST.get("family_type", "nuclear")
            if request.POST.get("family_size"):
                profile.family_size = int(request.POST.get("family_size"))

            # Note: Patient information is now handled through ElderProfile model
            # These fields have been removed from FamilyProfile

            # Home
            profile.pets_at_home = request.POST.get("pets_at_home") == "on"
            profile.pet_details = request.POST.get("pet_details", "")
            profile.smokers_in_home = request.POST.get("smokers_in_home") == "on"
            profile.accessibility_requirements = request.POST.get(
                "accessibility_requirements", ""
            )

            # Preferences
            profile.previous_caretaker = request.POST.get("previous_caretaker") == "on"
            profile.previous_caretaker_feedback = request.POST.get(
                "previous_caretaker_feedback", ""
            )
            profile.preferred_caretaker_gender = request.POST.get(
                "preferred_caretaker_gender", "any"
            )
            profile.preferred_language = request.POST.get("preferred_language", "")
            if request.POST.get("monthly_budget"):
                profile.monthly_budget = float(request.POST.get("monthly_budget"))

            # Documents
            if "identity_proof" in request.FILES:
                profile.identity_proof = request.FILES["identity_proof"]
            if "address_proof" in request.FILES:
                profile.address_proof = request.FILES["address_proof"]
            if "medical_reports" in request.FILES:
                profile.medical_reports = request.FILES["medical_reports"]

            profile.save()
            if request.user.phone != profile.phone:
                request.user.phone = profile.phone
                request.user.save()

            messages.success(request, "Profile updated successfully!")
            # FIXED: Added 'users:' namespace prefix
            return redirect("users:family_profile")

        except Exception as e:
            messages.error(request, f"Error updating profile: {str(e)}")

    context = {"profile": profile}
    return render(request, "users/update_family_profile.html", context)


# -------------------------------------------------------------------------
# Dashboard Views
# -------------------------------------------------------------------------
@login_required
def caretaker_dashboard(request):
    if request.user.role != "caretaker":
        messages.error(request, "Access denied.")
        return redirect("users:index")

    if not request.user.is_verified or request.user.verification_status != "verified":
        return redirect("users:verification_pending")

    try:
        profile = request.user.caretaker_profile
    except CaretakerProfile.DoesNotExist:
        profile = None

    total_applications = 0
    pending_applications = 0
    assigned_jobs = 0

    if CareApplication:
        applications = CareApplication.objects.filter(caretaker=request.user)
        total_applications = applications.count()
        pending_applications = applications.filter(status="pending").count()
        # Check the correct status for assigned jobs
        assigned_jobs = applications.filter(
            status="accepted"
        ).count()  # or "approved" depending on your model

    context = {
        "profile": profile,
        "total_applications": total_applications,
        "assigned_jobs": assigned_jobs,
        "pending_applications": pending_applications,
        "profile_strength": 100,
        "nearby_requests_count": 5,
        "today_assignment": None,
        "is_available_today": True,
    }
    return render(request, "users/caretaker_dashboard.html", context)


@login_required
def family_dashboard(request):
    if request.user.role != "family":
        messages.error(request, "Access denied.")
        return redirect("users:index")

    try:
        profile = request.user.family_profile
    except FamilyProfile.DoesNotExist:
        profile = None

    context = {"profile": profile}
    return render(request, "users/family_dashboard.html", context)


# -------------------------------------------------------------------------
# Elder Profile Views
# -------------------------------------------------------------------------
@login_required
def elder_list(request):
    if request.user.role != "family":
        messages.error(request, "Access denied.")
        return redirect("users:index")

    elders = ElderProfile.objects.filter(family=request.user).order_by(
        "-is_primary", "name"
    )
    context = {"elders": elders}
    return render(request, "users/elder_list.html", context)


@login_required
def elder_detail(request, elder_id):
    if request.user.role != "family":
        messages.error(request, "Access denied.")
        return redirect("users:index")

    elder = get_object_or_404(ElderProfile, id=elder_id, family=request.user)
    context = {"elder": elder}
    return render(request, "users/elder_detail.html", context)


def elder_add(request):
    if request.user.role != "family":
        messages.error(request, "Access denied.")
        return redirect("users:index")

    if request.method == "POST":
        try:
            elder = ElderProfile.objects.create(
                family=request.user,
                name=request.POST.get("name"),
                age=request.POST.get("age"),
                gender=request.POST.get("gender"),
                relationship=request.POST.get("relationship"),
                blood_group=request.POST.get("blood_group", ""),
                medical_conditions=request.POST.get("medical_conditions", ""),
                allergies=request.POST.get("allergies", ""),
                medications=request.POST.get("medications", ""),
                dietary_restrictions=request.POST.get("dietary_restrictions", ""),
                mobility_status=request.POST.get("mobility_status", "independent"),
                cognitive_status=request.POST.get("cognitive_status", "normal"),
                emergency_contact_name=request.POST.get("emergency_contact_name", ""),
                emergency_contact_phone=request.POST.get("emergency_contact_phone", ""),
                emergency_contact_relation=request.POST.get(
                    "emergency_contact_relation", ""
                ),
                notes=request.POST.get("notes", ""),
                is_primary=request.POST.get("is_primary") == "on",
            )

            try:
                family_profile = request.user.family_profile
                family_profile.elders.add(elder)
                family_profile.save()
            except FamilyProfile.DoesNotExist:
                family_profile = FamilyProfile.objects.create(user=request.user)
                family_profile.elders.add(elder)
                family_profile.save()

            if ElderProfile.objects.filter(family=request.user).count() == 1:
                elder.is_primary = True
                elder.save()

            messages.success(
                request, f"Elder profile for {elder.name} added successfully!"
            )
            return redirect("users:elder_list")
        except Exception as e:
            messages.error(request, f"Error adding elder: {str(e)}")

    # FIXED: Changed from "requests/elder_add.html" to "users/elder_add.html"
    return render(request, "users/elder_add.html")


@login_required
def elder_edit(request, elder_id):
    if request.user.role != "family":
        messages.error(request, "Access denied.")
        return redirect("users:index")

    elder = get_object_or_404(ElderProfile, id=elder_id, family=request.user)

    if request.method == "POST":
        try:
            elder.name = request.POST.get("name", elder.name)
            elder.age = request.POST.get("age", elder.age)
            elder.gender = request.POST.get("gender", elder.gender)
            elder.relationship = request.POST.get("relationship", elder.relationship)
            elder.blood_group = request.POST.get("blood_group", elder.blood_group)
            elder.medical_conditions = request.POST.get(
                "medical_conditions", elder.medical_conditions
            )
            elder.allergies = request.POST.get("allergies", elder.allergies)
            elder.medications = request.POST.get("medications", elder.medications)
            elder.dietary_restrictions = request.POST.get(
                "dietary_restrictions", elder.dietary_restrictions
            )
            elder.mobility_status = request.POST.get(
                "mobility_status", elder.mobility_status
            )
            elder.cognitive_status = request.POST.get(
                "cognitive_status", elder.cognitive_status
            )
            elder.emergency_contact_name = request.POST.get(
                "emergency_contact_name", elder.emergency_contact_name
            )
            elder.emergency_contact_phone = request.POST.get(
                "emergency_contact_phone", elder.emergency_contact_phone
            )
            elder.emergency_contact_relation = request.POST.get(
                "emergency_contact_relation", elder.emergency_contact_relation
            )
            elder.notes = request.POST.get("notes", elder.notes)

            new_primary = request.POST.get("is_primary") == "on"
            if new_primary and not elder.is_primary:
                elder.is_primary = True
            elif not new_primary and elder.is_primary:
                if ElderProfile.objects.filter(family=request.user).count() > 1:
                    elder.is_primary = False

            if "profile_picture" in request.FILES:
                elder.profile_picture = request.FILES["profile_picture"]

            elder.save()
            messages.success(
                request, f"Elder profile for {elder.name} updated successfully!"
            )
            return redirect("users:elder_detail", elder_id=elder.id)
        except Exception as e:
            messages.error(request, f"Error updating elder: {str(e)}")

    context = {"elder": elder}
    return render(request, "users/elder_edit.html", context)


@login_required
def elder_delete(request, elder_id):
    if request.user.role != "family":
        messages.error(request, "Access denied.")
        return redirect("users:index")

    elder = get_object_or_404(ElderProfile, id=elder_id, family=request.user)

    if request.method == "POST":
        name = elder.name
        was_primary = elder.is_primary
        elder.delete()

        if was_primary:
            remaining = ElderProfile.objects.filter(family=request.user).first()
            if remaining:
                remaining.is_primary = True
                remaining.save()
                messages.info(
                    request, f"{remaining.name} has been set as the new primary elder."
                )

        messages.success(request, f"Elder profile for {name} deleted successfully!")
        return redirect("users:elder_list")

    context = {"elder": elder}
    return render(request, "users/elder_confirm_delete.html", context)


@login_required
def elder_set_primary(request, elder_id):
    if request.user.role != "family":
        messages.error(request, "Access denied.")
        return redirect("users:index")

    elder = get_object_or_404(ElderProfile, id=elder_id, family=request.user)
    elder.is_primary = True
    elder.save()

    messages.success(request, f"{elder.name} is now the primary elder.")
    return redirect("users:elder_list")
