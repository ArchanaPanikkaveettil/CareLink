from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.db.models import Q, Count
from django.utils import timezone
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from .models import User, CaretakerProfile, FamilyProfile, CaretakerAvailability
from apps.Users.models import User, CaretakerProfile
from django.contrib.auth.decorators import login_required

User = get_user_model()
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
    return redirect("index")


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
            phone = request.POST.get("phone")  # This goes to User model

            # Basic validation
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
                return redirect("caretaker_register")

            if password != confirm_password:
                messages.error(request, "Passwords do not match.")
                return redirect("caretaker_register")

            if len(password) < 6:
                messages.error(request, "Password must be at least 6 characters.")
                return redirect("caretaker_register")

            # Check if username/email exists
            if (
                User.objects.filter(username=username).exists()
                or User.objects.filter(email=email).exists()
            ):
                messages.error(request, "Username or email already exists.")
                return redirect("caretaker_register")

            # ========== VERIFICATION FIELDS ==========
            date_of_birth = request.POST.get("date_of_birth")
            gender = request.POST.get("gender")

            # Professional verification documents
            certificate = request.FILES.get("certificate")
            identity_proof = request.FILES.get("identity_proof")
            qualification = request.POST.get("qualification")
            experience_years = request.POST.get("experience_years")

            # Address for background verification
            address = request.POST.get("address")
            city = request.POST.get("city")
            state = request.POST.get("state")
            pincode = request.POST.get("pincode")

            # Emergency contact
            emergency_name = request.POST.get("emergency_name")
            emergency_phone = request.POST.get("emergency_phone")
            emergency_relation = request.POST.get("emergency_relation")

            # ========== VALIDATE VERIFICATION FIELDS ==========
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
                return redirect("caretaker_register")

            # Terms acceptance
            accepted_terms = request.POST.get("accepted_terms") == "on"
            if not accepted_terms:
                messages.error(request, "You must accept the Terms and Conditions.")
                return redirect("caretaker_register")

            # Create user (phone goes in User model)
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                role="caretaker",
                is_verified=False,
                verification_status="pending",
                phone=phone,  # This is in User model
                accepted_terms=accepted_terms,
                accepted_terms_date=timezone.now(),
            )

            # Create caretaker profile (NO phone field here)
            profile = CaretakerProfile.objects.create(
                user=user,
                # Emergency contact
                emergency_contact_name=emergency_name,
                emergency_contact_phone=emergency_phone,
                emergency_contact_relation=emergency_relation,
                # Personal
                date_of_birth=date_of_birth,
                gender=gender,
                # Professional
                experience_years=experience_years,
                qualification=qualification,
                certificate=certificate,
                identity_proof=identity_proof,
                # Location
                address=address,
                city=city,
                state=state,
                pincode=pincode,
                country="India",
                # Default values
                skills="",
                languages="",
                bio="",
                availability_status="available",
                verified_by_admin=False,
            )

            messages.success(
                request,
                "Registration successful! Your documents are under verification. You'll be notified once verified.",
            )
            return redirect("login")

        except Exception as e:
            messages.error(request, f"Registration failed: {str(e)}")
            return redirect("caretaker_register")

    return render(request, "users/caretaker_register.html")


# -------------------------------------------------------------------------
# Family Registration
# -------------------------------------------------------------------------


def family_register(request):
    if request.method == "POST":
        try:
            # Get only essential registration data
            first_name = request.POST.get("first_name")
            last_name = request.POST.get("last_name")
            email = request.POST.get("email")
            password = request.POST.get("password")
            confirm_password = request.POST.get("confirm_password")
            phone = request.POST.get("phone")

            # Basic validation
            if not all(
                [first_name, last_name, email, password, confirm_password, phone]
            ):
                messages.error(request, "All fields are required.")
                return redirect("family_register")

            # Password validation
            if password != confirm_password:
                messages.error(request, "Passwords do not match.")
                return redirect("family_register")

            if len(password) < 6:
                messages.error(request, "Password must be at least 6 characters long.")
                return redirect("family_register")

            # Check if email already exists
            if User.objects.filter(username=email).exists():
                messages.error(
                    request,
                    "Email already registered. Please use another email or login.",
                )
                return redirect("family_register")

            # Terms acceptance
            accepted_terms = request.POST.get("accepted_terms") == "on"
            if not accepted_terms:
                messages.error(request, "You must accept the Terms and Conditions.")
                return redirect("family_register")

            # Create user (auto-verified)
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

            # Create basic family profile (only essential fields)
            FamilyProfile.objects.create(
                user=user,
                phone=phone,
                # Add minimal required fields with defaults
                address="",  # Will be filled later
                patient_name="",  # Will be filled later
                patient_age=None,  # Will be filled later
                primary_medical_condition="",  # Will be filled later
                care_required="",  # Will be filled later
            )

            messages.success(
                request,
                "Registration successful! You can now login. Please complete your profile after login.",
            )
            return redirect("login")

        except Exception as e:
            messages.error(request, f"Registration failed: {str(e)}")
            return redirect("family_register")

    return render(request, "users/family_register.html")


# -------------------------------------------------------------------------
# Custom Login (Role-Based Redirection)
# -------------------------------------------------------------------------

# -------------------------------------------------------------------------
# Custom Login (Role-Based Redirection with Admin Support)
# -------------------------------------------------------------------------


def custom_login(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

        # Authenticate user
        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)

            # Check if user is superuser/staff - redirect to custom admin
            if user.is_superuser or user.is_staff:
                return redirect(
                    "admin_dashboard"
                )  # This will now work with admin-panel/ prefix

            # Redirect based on user role
            if user.role == "family":
                return redirect("dashboard:family_dashboard")
            elif user.role == "caretaker":
                try:
                    if (
                        hasattr(user, "caretaker_profile")
                        and user.caretaker_profile.is_approved
                    ):
                        return redirect("dashboard:caretaker_dashboard")
                    else:
                        return redirect("verification_pending")
                except:
                    return redirect("verification_pending")
            else:
                return redirect("index")
        else:
            return render(
                request, "users/login.html", {"error": "Invalid email or password"}
            )

    return render(request, "users/login.html")


# -------------------------------------------------------------------------
# Custom Admin Dashboard
# -------------------------------------------------------------------------
# -------------------------------------------------------------------------
# ADMIN PANEL VIEWS
# -------------------------------------------------------------------------


@login_required
def admin_dashboard(request):
    """Custom admin dashboard for superusers and staff"""
    # Check if user is admin
    if not (request.user.is_superuser or request.user.is_staff):
        messages.error(request, "Access denied. Admin privileges required.")
        return redirect("index")

    # Get statistics
    total_users = User.objects.count()
    total_caretakers = User.objects.filter(role="caretaker").count()
    total_families = User.objects.filter(role="family").count()
    pending_verifications = User.objects.filter(
        role="caretaker", verification_status="pending"
    ).count()

    # Recent users
    recent_users = User.objects.order_by("-date_joined")[:10]

    # Pending verifications
    pending_caretakers = CaretakerProfile.objects.filter(
        user__verification_status="pending"
    ).select_related("user")[:10]

    context = {
        "total_users": total_users,
        "total_caretakers": total_caretakers,
        "total_families": total_families,
        "pending_verifications": pending_verifications,
        "pending_verifications_count": pending_verifications,
        "recent_users": recent_users,
        "pending_caretakers": pending_caretakers,
    }
    return render(request, "admin/admin_dashboard.html", context)


@login_required
def admin_users_list(request):
    """List all users with filters"""
    if not (request.user.is_superuser or request.user.is_staff):
        messages.error(request, "Access denied.")
        return redirect("index")

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

    if search_query:
        users = users.filter(
            Q(username__icontains=search_query)
            | Q(email__icontains=search_query)
            | Q(first_name__icontains=search_query)
            | Q(last_name__icontains=search_query)
        )

    # Pagination
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
        return redirect("index")

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

    # Pagination
    page = request.GET.get("page", 1)
    paginator = Paginator(caretakers, 20)

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
        return redirect("index")

    search_query = request.GET.get("q", "")

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

    # Pagination
    page = request.GET.get("page", 1)
    paginator = Paginator(families, 20)

    try:
        families = paginator.page(page)
    except PageNotAnInteger:
        families = paginator.page(1)
    except EmptyPage:
        families = paginator.page(paginator.num_pages)

    context = {
        "families": families,
        "search_query": search_query,
    }
    return render(request, "admin/admin_families_list.html", context)


@login_required
def admin_verifications(request):
    """List all pending verifications"""
    if not (request.user.is_superuser or request.user.is_staff):
        messages.error(request, "Access denied.")
        return redirect("index")

    pending_caretakers = (
        CaretakerProfile.objects.filter(user__verification_status="pending")
        .select_related("user")
        .order_by("user__date_joined")
    )

    # Pagination
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
        return redirect("index")

    caretaker = get_object_or_404(CaretakerProfile, id=id)

    if request.method == "POST":
        action = request.POST.get("action")
        remarks = request.POST.get("remarks", "")

        if action == "approve":
            caretaker.user.verification_status = "verified"
            caretaker.user.is_verified = True
            caretaker.verified_by_admin = True
            caretaker.verified_by = request.user
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
        return redirect("admin_verifications")

    # Get documents for display
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
        return redirect("index")

    user = get_object_or_404(User, id=id)

    # Get profile based on role
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
    """View all care requests (if you have a Requests app)"""
    if not (request.user.is_superuser or request.user.is_staff):
        messages.error(request, "Access denied.")
        return redirect("index")

    # This assumes you have a CareRequest model in your Requests app
    # You'll need to import it: from apps.Requests.models import CareRequest

    context = {
        # Add your care requests data here
    }
    return render(request, "admin/admin_requests.html", context)


from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.http import JsonResponse

# -------------------------------------------------------------------------
# Admin Password Change
# -------------------------------------------------------------------------


@login_required
def admin_change_password(request):
    """Change admin user password"""
    if not (request.user.is_superuser or request.user.is_staff):
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse(
                {"success": False, "error": "Access denied"}, status=403
            )
        messages.error(request, "Access denied.")
        return redirect("index")

    if request.method == "POST":
        current_password = request.POST.get("current_password")
        new_password = request.POST.get("new_password")
        confirm_password = request.POST.get("confirm_password")

        # Basic validation
        if not all([current_password, new_password, confirm_password]):
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return JsonResponse(
                    {"success": False, "error": "All fields are required"}
                )
            messages.error(request, "All fields are required.")
            return redirect("admin_profile")

        # Check current password
        if not request.user.check_password(current_password):
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return JsonResponse(
                    {"success": False, "error": "Current password is incorrect"}
                )
            messages.error(request, "Current password is incorrect.")
            return redirect("admin_profile")

        # Check new password match
        if new_password != confirm_password:
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return JsonResponse(
                    {"success": False, "error": "New passwords do not match"}
                )
            messages.error(request, "New passwords do not match.")
            return redirect("admin_profile")

        # Password strength validation
        if len(new_password) < 8:
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return JsonResponse(
                    {
                        "success": False,
                        "error": "Password must be at least 8 characters long",
                    }
                )
            messages.error(request, "Password must be at least 8 characters long.")
            return redirect("admin_profile")

        if not any(char.isdigit() for char in new_password):
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return JsonResponse(
                    {
                        "success": False,
                        "error": "Password must contain at least one number",
                    }
                )
            messages.error(request, "Password must contain at least one number.")
            return redirect("admin_profile")

        if not any(char in "!@#$%^&*()_+-=[]{}|;:,.<>?" for char in new_password):
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return JsonResponse(
                    {
                        "success": False,
                        "error": "Password must contain at least one special character",
                    }
                )
            messages.error(
                request, "Password must contain at least one special character."
            )
            return redirect("admin_profile")

        # Check if new password is same as old
        if current_password == new_password:
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return JsonResponse(
                    {
                        "success": False,
                        "error": "New password cannot be the same as current password",
                    }
                )
            messages.error(
                request, "New password cannot be the same as current password."
            )
            return redirect("admin_profile")

        try:
            # Set new password
            request.user.set_password(new_password)
            request.user.save()

            # Keep the user logged in
            update_session_auth_hash(request, request.user)

            # Log the password change (you can create an AuditLog model for this)
            # AuditLog.objects.create(
            #     user=request.user,
            #     action='PASSWORD_CHANGE',
            #     details='Admin user changed password'
            # )

            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return JsonResponse(
                    {"success": True, "message": "Password changed successfully"}
                )

            messages.success(request, "Password changed successfully.")
            return redirect("admin_profile")

        except Exception as e:
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return JsonResponse({"success": False, "error": str(e)})
            messages.error(request, f"Error changing password: {str(e)}")
            return redirect("admin_profile")

    # GET request - redirect to profile
    return redirect("admin_profile")


# -------------------------------------------------------------------------
# Admin Logout All Sessions
# -------------------------------------------------------------------------


@login_required
def admin_logout_all_sessions(request):
    """Logout all other sessions for the admin user"""
    if not (request.user.is_superuser or request.user.is_staff):
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse(
                {"success": False, "error": "Access denied"}, status=403
            )
        messages.error(request, "Access denied.")
        return redirect("index")

    if request.method == "POST":
        try:
            # Get current session key
            current_session = request.session.session_key

            # Get all sessions for this user (requires django-user-sessions or similar)
            # This is a placeholder - implement based on your session backend
            from django.contrib.sessions.models import Session

            # Get all user sessions
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

            # Delete other sessions
            for session_key in user_sessions:
                Session.objects.filter(session_key=session_key).delete()

            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return JsonResponse(
                    {
                        "success": True,
                        "message": f"Logged out {len(user_sessions)} other sessions",
                    }
                )

            messages.success(
                request, f"Logged out {len(user_sessions)} other sessions."
            )
            return redirect("admin_profile")

        except Exception as e:
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return JsonResponse({"success": False, "error": str(e)})
            messages.error(request, f"Error logging out sessions: {str(e)}")
            return redirect("admin_profile")

    return redirect("admin_profile")


# -------------------------------------------------------------------------
# Admin Quick View (AJAX)
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
            "dob": caretaker.date_of_birth or "Not provided",
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
def admin_applications(request):
    """View all applications"""
    if not (request.user.is_superuser or request.user.is_staff):
        messages.error(request, "Access denied.")
        return redirect("index")

    # This assumes you have an Application model in your Applications app

    context = {
        # Add your applications data here
    }
    return render(request, "admin/admin_applications.html", context)


@login_required
def admin_reports(request):
    """Generate and view reports"""
    if not (request.user.is_superuser or request.user.is_staff):
        messages.error(request, "Access denied.")
        return redirect("index")

    # Get date range from request
    start_date = request.GET.get("start_date")
    end_date = request.GET.get("end_date")
    report_type = request.GET.get("type", "users")

    context = {
        "start_date": start_date,
        "end_date": end_date,
        "report_type": report_type,
    }
    return render(request, "admin/admin_reports.html", context)


@login_required
def admin_audit_logs(request):
    """View system audit logs"""
    if not (request.user.is_superuser):
        messages.error(request, "Access denied. Superuser privileges required.")
        return redirect("admin_dashboard")

    # You would need an AuditLog model for this
    # For now, we'll pass empty data

    context = {}
    return render(request, "admin/admin_audit_logs.html", context)


@login_required
def admin_profile(request):
    """Admin profile settings"""
    if not (request.user.is_superuser or request.user.is_staff):
        messages.error(request, "Access denied.")
        return redirect("index")

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
        return redirect("admin_profile")

    context = {
        "admin_user": request.user,
    }
    return render(request, "admin/admin_profile.html", context)


@login_required
def admin_settings(request):
    """Admin system settings"""
    if not (request.user.is_superuser):
        messages.error(request, "Access denied. Superuser privileges required.")
        return redirect("admin_dashboard")

    if request.method == "POST":
        # Handle settings update
        # This could include site settings, email templates, etc.
        messages.success(request, "Settings updated successfully.")
        return redirect("admin_settings")

    context = {}
    return render(request, "admin/admin_settings.html")


@login_required
def admin_toggle_user_status(request, id):
    """Enable/disable user account"""
    if not (request.user.is_superuser):
        messages.error(request, "Access denied. Superuser privileges required.")
        return redirect("admin_dashboard")

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

    return redirect("admin_user_detail", id=id)


# -------------------------------------------------------------------------
# Caretaker Profile Views
# -------------------------------------------------------------------------


@login_required
def caretaker_profile(request):
    if request.user.role != "caretaker":
        messages.error(request, "Access denied. This page is for caretakers only.")
        return redirect("index")

    try:
        profile = request.user.caretaker_profile

        # Process skills and languages for template
        skills_list = []
        if profile.skills:
            skills_list = [
                skill.strip() for skill in profile.skills.split(",") if skill.strip()
            ]

        languages_list = []
        if profile.languages:
            languages_list = [
                lang.strip() for lang in profile.languages.split(",") if lang.strip()
            ]

    except CaretakerProfile.DoesNotExist:
        profile = CaretakerProfile.objects.create(
            user=request.user, address=""  # Remove phone from here
        )
        skills_list = []
        languages_list = []
        messages.info(request, "Please complete your profile information.")

    # Get availability schedule
    availability = profile.availability_schedule.all().order_by("day_of_week")

    context = {
        "profile": profile,
        "user": request.user,  # Pass user to access phone
        "availability": availability,
        "skills_list": skills_list,
        "languages_list": languages_list,
    }
    return render(request, "users/caretaker_profile.html", context)


# -------------------------------------------------------------------------
# Caretaker Profile Update View
# -------------------------------------------------------------------------


@login_required
def update_caretaker_profile(request):
    """Update caretaker profile with detailed information"""
    if request.user.role != "caretaker":
        messages.error(request, "Access denied.")
        return redirect("index")

    # Get or create profile
    try:
        profile = request.user.caretaker_profile
    except CaretakerProfile.DoesNotExist:
        profile = CaretakerProfile.objects.create(
            user=request.user
            # Remove phone from here
        )

    if request.method == "POST":
        try:
            # ========== PERSONAL INFORMATION ==========
            date_of_birth = request.POST.get("date_of_birth")
            if date_of_birth:
                profile.date_of_birth = date_of_birth

            profile.gender = request.POST.get("gender", profile.gender)

            # ========== CONTACT INFORMATION ==========
            # Update User model's phone field (NOT profile)
            request.user.phone = request.POST.get("phone", request.user.phone)

            # Emergency contact (these ARE in CaretakerProfile)
            profile.emergency_contact_name = request.POST.get(
                "emergency_contact_name", ""
            )
            profile.emergency_contact_phone = request.POST.get(
                "emergency_contact_phone", ""
            )
            profile.emergency_contact_relation = request.POST.get(
                "emergency_contact_relation", ""
            )

            # ========== PROFESSIONAL INFORMATION ==========
            experience_years = request.POST.get("experience_years")
            if experience_years:
                profile.experience_years = int(experience_years)

            profile.experience_level = request.POST.get("experience_level", "entry")
            profile.qualification = request.POST.get("qualification", "")
            profile.specialized_training = request.POST.get("specialized_training", "")

            # Skills and languages
            profile.skills = request.POST.get("skills", "")
            profile.languages = request.POST.get("languages", "")
            profile.employment_type = request.POST.get("employment_type", "full_time")

            # ========== PROFESSIONAL SUMMARY ==========
            profile.bio = request.POST.get("bio", "")
            profile.achievements = request.POST.get("achievements", "")

            # ========== AVAILABILITY ==========
            profile.availability_status = request.POST.get(
                "availability_status", "available"
            )
            profile.preferred_shift = request.POST.get("preferred_shift", "flexible")
            profile.willing_to_relocate = (
                request.POST.get("willing_to_relocate") == "on"
            )

            max_distance = request.POST.get("max_travel_distance")
            if max_distance:
                profile.max_travel_distance = int(max_distance)

            # ========== LOCATION ==========
            profile.address = request.POST.get("address", "")
            profile.city = request.POST.get("city", "")
            profile.state = request.POST.get("state", "")
            profile.country = request.POST.get("country", "India")
            profile.pincode = request.POST.get("pincode", "")

            # ========== DOCUMENTS (Optional updates) ==========
            if "resume" in request.FILES:
                profile.resume = request.FILES["resume"]
            if "background_check" in request.FILES:
                profile.background_check = request.FILES["background_check"]
            if "profile_picture" in request.FILES:
                request.user.profile_picture = request.FILES["profile_picture"]

            # Save both profile and user
            profile.save()
            request.user.save()

            # ========== AVAILABILITY SCHEDULE ==========
            # Clear existing availability
            profile.availability_schedule.all().delete()

            # Save new availability
            days = [
                "monday",
                "tuesday",
                "wednesday",
                "thursday",
                "friday",
                "saturday",
                "sunday",
            ]
            day_map = {
                "monday": 0,
                "tuesday": 1,
                "wednesday": 2,
                "thursday": 3,
                "friday": 4,
                "saturday": 5,
                "sunday": 6,
            }

            for day in days:
                available = request.POST.get(f"{day}_available") == "on"
                if available:
                    start_time = request.POST.get(f"{day}_start")
                    end_time = request.POST.get(f"{day}_end")

                    if start_time and end_time:
                        CaretakerAvailability.objects.create(
                            caretaker=profile,
                            day_of_week=day_map[day],
                            start_time=start_time,
                            end_time=end_time,
                            is_available=True,
                        )

            messages.success(request, "Profile updated successfully!")
            return redirect("caretaker_profile")

        except Exception as e:
            messages.error(request, f"Error updating profile: {str(e)}")
            # Print error for debugging
            print(f"ERROR in profile update: {str(e)}")
            import traceback

            traceback.print_exc()

    # GET request - display the form
    # Get existing availability for form
    availability_dict = {}
    for avail in profile.availability_schedule.all():
        days = [
            "monday",
            "tuesday",
            "wednesday",
            "thursday",
            "friday",
            "saturday",
            "sunday",
        ]
        day_name = days[avail.day_of_week]
        availability_dict[day_name] = {
            "available": True,
            "start": avail.start_time.strftime("%H:%M") if avail.start_time else "",
            "end": avail.end_time.strftime("%H:%M") if avail.end_time else "",
        }

    # Create context with individual variables for each day
    context = {
        "profile": profile,
    }

    # Add individual day variables for the template
    days = [
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
        "saturday",
        "sunday",
    ]
    for day in days:
        if day in availability_dict:
            context[f"{day}_available"] = True
            context[f"{day}_start"] = availability_dict[day]["start"]
            context[f"{day}_end"] = availability_dict[day]["end"]
        else:
            context[f"{day}_available"] = False
            context[f"{day}_start"] = ""
            context[f"{day}_end"] = ""

    return render(request, "users/update_caretaker_profile.html", context)


# -------------------------------------------------------------------------
# Verification Pending Page (Caretaker)
# -------------------------------------------------------------------------


@login_required
def verification_pending(request):
    if request.user.role != "caretaker":
        return redirect("index")

    if request.user.is_verified:
        # Fix: Use the correct URL name with namespace
        return redirect("dashboard:caretaker_dashboard")  # Add 'dashboard:' namespace

    return render(request, "users/verification_pending.html")


# -------------------------------------------------------------------------
# Search Caretakers (Family)
# -------------------------------------------------------------------------


@login_required
def search_caretakers(request):
    # Only families can search
    if request.user.role != "family":
        messages.error(
            request, "Access denied. Only families can search for caretakers."
        )
        return redirect("index")

    # Get all verified caretakers
    caretakers = CaretakerProfile.objects.filter(
        user__role="caretaker", user__is_verified=True
    ).select_related("user")

    # Apply filters
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

    return render(
        request,
        "users/search_caretakers.html",
        {
            "caretakers": caretakers,
        },
    )


# -------------------------------------------------------------------------
# Caretaker Detail View
# -------------------------------------------------------------------------


@login_required
def caretaker_detail(request, id):
    """View caretaker profile details"""
    # Get the caretaker user
    caretaker = get_object_or_404(User, id=id, role="caretaker")

    # Try to get the profile, but don't fail if it doesn't exist
    try:
        profile = CaretakerProfile.objects.get(user=caretaker)
    except CaretakerProfile.DoesNotExist:
        profile = None

    context = {
        "caretaker": caretaker,
        "profile": profile,
    }
    return render(request, "users/caretaker_detail.html", context)


# -------------------------------------------------------------------------
# Family Profile Views
# -------------------------------------------------------------------------


@login_required
def family_profile(request):
    """View and display family profile"""
    if request.user.role != "family":
        messages.error(request, "Access denied. This page is for family members only.")
        return redirect("index")

    try:
        profile = request.user.family_profile
    except FamilyProfile.DoesNotExist:
        # Create profile if it doesn't exist
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

    # ========== DYNAMIC STATISTICS FROM DATABASE ==========
    from apps.Requests.models import CareRequest
    from django.db.models import Count, Q

    # Get all requests by this family
    user_requests = CareRequest.objects.filter(family=request.user)

    # Calculate statistics
    total_requests = user_requests.count()
    open_requests = user_requests.filter(status="open").count()
    draft_requests = user_requests.filter(status="draft").count()
    assigned_requests = user_requests.filter(status="assigned").count()
    closed_requests = user_requests.filter(status="closed").count()

    # Calculate total applications across all requests
    total_applications = 0
    for req in user_requests:
        # If you have applications_count field
        if hasattr(req, "applications_count"):
            total_applications += req.applications_count or 0
        # Or if you have a related name for applications
        elif hasattr(req, "applications"):
            total_applications += req.applications.count()

    # Debug print to check values
    print(f"DEBUG - User: {request.user.username}")
    print(f"DEBUG - Total Requests: {total_requests}")
    print(f"DEBUG - Open Requests: {open_requests}")
    print(f"DEBUG - Total Applications: {total_applications}")

    context = {
        "profile": profile,
        "user": request.user,
        # Statistics - THESE ARE THE VARIABLES YOUR TEMPLATE USES
        "total_requests": total_requests,
        "open_requests": open_requests,
        "total_applications": total_applications,  # Template uses this
    }
    return render(request, "users/family_profile.html", context)


# -----------------------------------
# Update Family Profile
# -----------------------------------


@login_required
def update_family_profile(request):
    """Update family profile with detailed information"""
    if request.user.role != "family":
        messages.error(request, "Access denied.")
        return redirect("index")

    # Get or create profile
    try:
        profile = request.user.family_profile
    except FamilyProfile.DoesNotExist:
        profile = FamilyProfile.objects.create(
            user=request.user, phone=request.user.phone or ""
        )

    if request.method == "POST":
        try:

            # ========== CONTACT INFORMATION ==========
            profile.phone = request.POST.get("phone", "")
            profile.alternate_phone = request.POST.get("alternate_phone", "")

            # Emergency contact - split into separate fields
            profile.emergency_contact_name = request.POST.get(
                "emergency_contact_name", ""
            )
            profile.emergency_contact_phone = request.POST.get(
                "emergency_contact_phone", ""
            )
            profile.emergency_contact_relation = request.POST.get(
                "emergency_contact_relation", ""
            )

            # ========== ADDRESS DETAILS ==========
            profile.address = request.POST.get("address", "")
            profile.city = request.POST.get("city", "")
            profile.state = request.POST.get("state", "")
            profile.country = request.POST.get("country", "India")
            profile.pincode = request.POST.get("pincode", "")
            profile.landmark = request.POST.get("landmark", "")
            profile.residence_type = request.POST.get("residence_type", "apartment")

            # ========== FAMILY INFORMATION ==========
            profile.family_type = request.POST.get("family_type", "nuclear")

            family_size = request.POST.get("family_size")
            if family_size:
                profile.family_size = int(family_size)

            # ========== PATIENT INFORMATION ==========
            profile.patient_name = request.POST.get("patient_name", "")

            patient_age = request.POST.get("patient_age")
            if patient_age:
                profile.patient_age = int(patient_age)
            else:
                profile.patient_age = None

            profile.patient_gender = request.POST.get("patient_gender", "")
            profile.patient_blood_group = request.POST.get("patient_blood_group", "")

            # ========== MEDICAL INFORMATION ==========
            profile.primary_medical_condition = request.POST.get(
                "primary_medical_condition", ""
            )
            profile.secondary_conditions = request.POST.get("secondary_conditions", "")
            profile.allergies = request.POST.get("allergies", "")
            profile.medications = request.POST.get("medications", "")
            profile.dietary_restrictions = request.POST.get("dietary_restrictions", "")

            # ========== CARE REQUIREMENTS ==========
            profile.care_required = request.POST.get("care_required", "")
            profile.care_frequency = request.POST.get("care_frequency", "daily")

            # ========== HOME ENVIRONMENT ==========
            profile.pets_at_home = request.POST.get("pets_at_home") == "on"
            profile.pet_details = request.POST.get("pet_details", "")
            profile.smokers_in_home = request.POST.get("smokers_in_home") == "on"
            profile.accessibility_requirements = request.POST.get(
                "accessibility_requirements", ""
            )

            # ========== PREVIOUS CARETAKER ==========
            profile.previous_caretaker = request.POST.get("previous_caretaker") == "on"
            profile.previous_caretaker_feedback = request.POST.get(
                "previous_caretaker_feedback", ""
            )

            # ========== PREFERENCES ==========
            profile.preferred_caretaker_gender = request.POST.get(
                "preferred_caretaker_gender", "any"
            )
            profile.preferred_language = request.POST.get("preferred_language", "")

            monthly_budget = request.POST.get("monthly_budget")
            if monthly_budget:
                profile.monthly_budget = float(monthly_budget)
            else:
                profile.monthly_budget = None

            # ========== DOCUMENTS (File Uploads) ==========
            if "identity_proof" in request.FILES:
                profile.identity_proof = request.FILES["identity_proof"]
            if "address_proof" in request.FILES:
                profile.address_proof = request.FILES["address_proof"]
            if "medical_reports" in request.FILES:
                profile.medical_reports = request.FILES["medical_reports"]

            # Save the profile
            profile.save()

            # Update user phone if changed
            if request.user.phone != profile.phone:
                request.user.phone = profile.phone
                request.user.save()

            messages.success(request, "Profile updated successfully!")
            return redirect("family_profile")

        except Exception as e:
            messages.error(request, f"Error updating profile: {str(e)}")
            # Print error for debugging
            print(f"ERROR in profile update: {str(e)}")
            import traceback

            traceback.print_exc()

    context = {"profile": profile}
    return render(request, "users/update_family_profile.html", context)


# -------------------------------------------------------------------------
# Dashboard Views
# -------------------------------------------------------------------------


@login_required
def caretaker_dashboard(request):
    """Caretaker dashboard view"""
    if request.user.role != "caretaker":
        messages.error(request, "Access denied.")
        return redirect("index")

    # Clear any messages from previous pages (like login)
    storage = messages.get_messages(request)
    storage.used = True

    # Check verification status
    if not request.user.is_verified or request.user.verification_status != "verified":
        return redirect("verification_pending")

    try:
        profile = request.user.caretaker_profile
    except CaretakerProfile.DoesNotExist:
        profile = None

    # Get statistics - update these with actual data from your apps
    total_applications = 0  # This would come from applications app
    assigned_jobs = 0  # This would come from assignments app
    pending_applications = 0  # This would come from applications app

    context = {
        "profile": profile,
        "total_applications": total_applications,
        "assigned_jobs": assigned_jobs,
        "pending_applications": pending_applications,
    }
    return render(
        request, "users/caretaker_dashboard.html", context
    )  # Note: using 'users/' prefix


@login_required
def family_dashboard(request):
    """Family dashboard view"""
    if request.user.role != "family":
        messages.error(request, "Access denied.")
        return redirect("index")

    # Clear any messages from previous pages (like login)
    storage = messages.get_messages(request)
    storage.used = True

    try:
        profile = request.user.family_profile
    except FamilyProfile.DoesNotExist:
        profile = None

    context = {
        "profile": profile,
    }
    return render(
        request, "users/family_dashboard.html", context
    )  # Note: using 'users/' prefix

    """Family dashboard view"""
    if request.user.role != "family":
        messages.error(request, "Access denied.")
        return redirect("index")

    # Clear any messages from previous pages (like login)
    storage = messages.get_messages(request)
    storage.used = True

    try:
        profile = request.user.family_profile
    except FamilyProfile.DoesNotExist:
        profile = None

    context = {
        "profile": profile,
    }
    return render(request, "users/family_dashboard.html", context)


# -------------------------------------------------------------------------
# Elder Profile Views
# -------------------------------------------------------------------------

from .models import ElderProfile


@login_required
def elder_list(request):
    """List all elders for the family"""
    if request.user.role != "family":
        messages.error(request, "Access denied.")
        return redirect("index")

    elders = ElderProfile.objects.filter(family=request.user).order_by(
        "-is_primary", "name"
    )

    context = {
        "elders": elders,
    }
    return render(request, "users/elder_list.html", context)


@login_required
def elder_detail(request, elder_id):
    """View elder details"""
    if request.user.role != "family":
        messages.error(request, "Access denied.")
        return redirect("index")

    elder = get_object_or_404(ElderProfile, id=elder_id, family=request.user)

    context = {
        "elder": elder,
    }
    return render(request, "users/elder_detail.html", context)


@login_required
def elder_add(request):
    """Add a new elder"""
    if request.user.role != 'family':
        messages.error(request, "Access denied.")
        return redirect('index')
    
    if request.method == 'POST':
        try:
            elder = ElderProfile.objects.create(
                family=request.user,
                name=request.POST.get('name'),
                age=request.POST.get('age'),
                gender=request.POST.get('gender'),
                relationship=request.POST.get('relationship'),
                blood_group=request.POST.get('blood_group', ''),
                medical_conditions=request.POST.get('medical_conditions', ''),
                allergies=request.POST.get('allergies', ''),
                medications=request.POST.get('medications', ''),
                dietary_restrictions=request.POST.get('dietary_restrictions', ''),
                mobility_status=request.POST.get('mobility_status', 'independent'),
                cognitive_status=request.POST.get('cognitive_status', 'normal'),
                emergency_contact_name=request.POST.get('emergency_contact_name', ''),
                emergency_contact_phone=request.POST.get('emergency_contact_phone', ''),
                emergency_contact_relation=request.POST.get('emergency_contact_relation', ''),
                notes=request.POST.get('notes', ''),
                is_primary=request.POST.get('is_primary') == 'on',
            )
            
            # Add elder to family profile's elders list
            try:
                family_profile = request.user.family_profile
                family_profile.elders.add(elder)
                family_profile.save()
            except FamilyProfile.DoesNotExist:
                # Create family profile if it doesn't exist
                family_profile = FamilyProfile.objects.create(user=request.user)
                family_profile.elders.add(elder)
                family_profile.save()
            
            # If this is the first elder, automatically set as primary
            if ElderProfile.objects.filter(family=request.user).count() == 1:
                elder.is_primary = True
                elder.save()
            
            messages.success(request, f"Elder profile for {elder.name} added successfully!")
            return redirect('elder_list')
        except Exception as e:
            messages.error(request, f"Error adding elder: {str(e)}")
    
    return render(request, 'users/elder_add.html')



@login_required
def elder_edit(request, elder_id):
    """Edit elder profile"""
    if request.user.role != "family":
        messages.error(request, "Access denied.")
        return redirect("index")

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

            # Handle primary status
            new_primary = request.POST.get("is_primary") == "on"
            if new_primary and not elder.is_primary:
                # Set this as primary, which will unset others via model's save method
                elder.is_primary = True
            elif not new_primary and elder.is_primary:
                # Check if this is the only elder
                if ElderProfile.objects.filter(family=request.user).count() > 1:
                    elder.is_primary = False
                else:
                    messages.warning(
                        request, "Cannot unset primary as this is the only elder."
                    )

            # Handle profile picture
            if "profile_picture" in request.FILES:
                elder.profile_picture = request.FILES["profile_picture"]

            elder.save()
            messages.success(
                request, f"Elder profile for {elder.name} updated successfully!"
            )
            return redirect("elder_detail", elder_id=elder.id)
        except Exception as e:
            messages.error(request, f"Error updating elder: {str(e)}")

    context = {
        "elder": elder,
    }
    return render(request, "users/elder_edit.html", context)


@login_required
def elder_delete(request, elder_id):
    """Delete elder profile"""
    if request.user.role != "family":
        messages.error(request, "Access denied.")
        return redirect("index")

    elder = get_object_or_404(ElderProfile, id=elder_id, family=request.user)

    if request.method == "POST":
        name = elder.name
        was_primary = elder.is_primary
        elder.delete()

        # If we deleted the primary elder, set another as primary
        if was_primary:
            remaining = ElderProfile.objects.filter(family=request.user).first()
            if remaining:
                remaining.is_primary = True
                remaining.save()
                messages.info(
                    request, f"{remaining.name} has been set as the new primary elder."
                )

        messages.success(request, f"Elder profile for {name} deleted successfully!")
        return redirect("elder_list")

    context = {
        "elder": elder,
    }
    return render(request, "users/elder_confirm_delete.html", context)


@login_required
def elder_set_primary(request, elder_id):
    """Set an elder as primary"""
    if request.user.role != "family":
        messages.error(request, "Access denied.")
        return redirect("index")

    elder = get_object_or_404(ElderProfile, id=elder_id, family=request.user)

    # Set this as primary (model save will handle unsetting others)
    elder.is_primary = True
    elder.save()

    messages.success(request, f"{elder.name} is now the primary elder.")
    return redirect("elder_list")
