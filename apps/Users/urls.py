from django.urls import path
from . import views

urlpatterns = [
    # Home / Landing Page
    path("", views.index, name="index"),
    # Login
    path("login/", views.custom_login, name="login"),
    # logout
    path("logout/", views.custom_logout, name="logout"),
    # Registration
    path("register/family/", views.family_register, name="family_register"),
    path("register/caretaker/", views.caretaker_register, name="caretaker_register"),
    # Verification page (for unapproved caretakers)
    path(
        "verification-pending/", views.verification_pending, name="verification_pending"
    ),
    # Search caretakers (Family feature)
    path("search-caretakers/", views.search_caretakers, name="search_caretakers"),
    # View caretaker details
    path("caretaker/<int:id>/", views.caretaker_detail, name="caretaker_detail"),
    path("profile/family/", views.family_profile, name="family_profile"),
    path(
        "profile/family/update/",
        views.update_family_profile,
        name="update_family_profile",
    ),
    path("profile/caretaker/", views.caretaker_profile, name="caretaker_profile"),
    path(
        "profile/caretaker/update/",
        views.update_caretaker_profile,
        name="update_caretaker_profile",
    ),
    path("admin/dashboard/", views.admin_dashboard, name="admin_dashboard"),
    # User Management
    path("admin-panel/dashboard/", views.admin_dashboard, name="admin_dashboard"),
    # User Management
    path("admin-panel/users/", views.admin_users_list, name="admin_users_list"),
    path(
        "admin-panel/caretakers/",
        views.admin_caretakers_list,
        name="admin_caretakers_list",
    ),
    path(
        "admin-panel/families/", views.admin_families_list, name="admin_families_list"
    ),
    path(
        "admin-panel/user/<int:id>/", views.admin_user_detail, name="admin_user_detail"
    ),
    path(
        "admin-panel/user/<int:id>/toggle-status/",
        views.admin_toggle_user_status,
        name="admin_toggle_user_status",
    ),
    # Verification
    path(
        "admin-panel/verifications/",
        views.admin_verifications,
        name="admin_verifications",
    ),
    path(
        "admin-panel/verify-caretaker/<int:id>/",
        views.admin_verify_caretaker,
        name="admin_verify_caretaker",
    ),
    # Requests & Applications
    path("admin-panel/requests/", views.admin_requests, name="admin_requests"),
    path(
        "admin-panel/applications/", views.admin_applications, name="admin_applications"
    ),
    # Reports & Logs
    path("admin-panel/reports/", views.admin_reports, name="admin_reports"),
    path("admin-panel/audit-logs/", views.admin_audit_logs, name="admin_audit_logs"),
    # Admin Profile & Settings
    path("admin-panel/profile/", views.admin_profile, name="admin_profile"),
    path("admin-panel/settings/", views.admin_settings, name="admin_settings"),
    path(
        "admin-panel/change-password/",
        views.admin_change_password,
        name="admin_change_password",
    ),
    # Admin Logout All Sessions
    path(
        "admin-panel/logout-all-sessions/",
        views.admin_logout_all_sessions,
        name="admin_logout_all_sessions",
    ),
    # Admin Quick View AJAX
    path(
        "admin-panel/verify-caretaker/<int:id>/quick-view/",
        views.admin_quick_view_caretaker,
        name="admin_quick_view_caretaker",
    ),
]
