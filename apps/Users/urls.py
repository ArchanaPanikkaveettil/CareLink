from django.urls import path
from . import views

app_name = "users"

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
    # ========== ADMIN PANEL URLS ==========
    # Dashboard
    path("admin/dashboard/", views.admin_dashboard, name="admin_dashboard"),
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
        "admin-panel/user/<int:id>/edit/", views.admin_user_edit, name="admin_user_edit"
    ),
    path(
        "admin-panel/user/<int:id>/delete/",
        views.admin_user_delete,
        name="admin_user_delete",
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
    path(
        "admin-panel/verify-caretaker/<int:id>/quick-view/",
        views.admin_quick_view_caretaker,
        name="admin_quick_view_caretaker",
    ),
    path("admin-panel/bulk-verify/", views.admin_bulk_verify, name="admin_bulk_verify"),
    # Requests & Applications
    path("admin-panel/requests/", views.admin_requests, name="admin_requests"),
    path(
        "admin-panel/request/<int:request_id>/",
        views.admin_request_detail,
        name="admin_request_detail",
    ),
    path(
        "admin-panel/applications/", views.admin_applications, name="admin_applications"
    ),
    path(
        "admin-panel/application/<int:app_id>/",
        views.admin_application_detail,
        name="admin_application_detail",
    ),
    # Reports & Logs
    path("admin-panel/reports/", views.admin_reports, name="admin_reports"),
    path("admin-panel/audit-logs/", views.admin_audit_logs, name="admin_audit_logs"),
    path("admin-panel/export-data/", views.admin_export_data, name="admin_export_data"),
    path(
        "admin-panel/clear-old-logs/",
        views.admin_clear_old_logs,
        name="admin_clear_old_logs",
    ),
    # Admin Profile & Settings
    path("admin-panel/profile/", views.admin_profile, name="admin_profile"),
    path("admin-panel/settings/", views.admin_settings, name="admin_settings"),
    path(
        "admin-panel/change-password/",
        views.admin_change_password,
        name="admin_change_password",
    ),
    path(
        "admin-panel/logout-all-sessions/",
        views.admin_logout_all_sessions,
        name="admin_logout_all_sessions",
    ),
    # System
    path(
        "admin-panel/system-health/",
        views.admin_system_health,
        name="admin_system_health",
    ),
    path("admin-panel/test/", views.admin_test, name="admin_test"),
    # ========== ELDER PROFILE URLS ==========
    path("elders/", views.elder_list, name="elder_list"),
    path("elders/add/", views.elder_add, name="elder_add"),
    path("elders/<int:elder_id>/", views.elder_detail, name="elder_detail"),
    path("elders/<int:elder_id>/edit/", views.elder_edit, name="elder_edit"),
    path("elders/<int:elder_id>/delete/", views.elder_delete, name="elder_delete"),
    path(
        "elders/<int:elder_id>/set-primary/",
        views.elder_set_primary,
        name="elder_set_primary",
    ),
]
