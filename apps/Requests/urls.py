from django.urls import path
from . import views

app_name = "requests"

urlpatterns = [
    # ============================================================================
    # FAMILY URLs - Care Request Management
    # ============================================================================
    # Create and manage requests
    path("post/", views.post_request, name="post_request"),
    path("my-requests/", views.my_requests, name="my_requests"),
    path("<int:request_id>/", views.request_detail, name="request_detail"),
    path("<int:request_id>/edit/", views.edit_request, name="edit_request"),
    path("<int:request_id>/publish/", views.publish_request, name="publish_request"),
    path("<int:request_id>/close/", views.close_request, name="close_request"),
    path("<int:request_id>/delete/", views.delete_request, name="delete_request"),
    path("<int:request_id>/save-draft/", views.save_draft, name="save_draft"),
    path("find-caretakers/", views.find_caretakers, name="find_caretakers"),
    path(
        "caretaker/<int:caretaker_id>/", views.caretaker_detail, name="caretaker_detail"
    ),
    path(
        "caretaker/<int:caretaker_id>/availability/",
        views.view_caretaker_availability,
        name="view_caretaker_availability",
    ),
    # ============================================================================
    # CARETAKER URLs - Browse and Apply
    # ============================================================================
    # Browse and apply
    path("browse/", views.browse_requests, name="browse_requests"),
    path("<int:request_id>/apply/", views.apply_for_request, name="apply_for_request"),
    # ============================================================================
    # BOOKING & AVAILABILITY URLs
    # ============================================================================
    # Availability calendar (view only)
    path(
        "caretaker/<int:caretaker_id>/availability/",
        views.view_caretaker_availability,
        name="caretaker_availability",
    ),
    # Booking actions
    path(
        "caretaker/<int:caretaker_id>/book/<int:request_id>/",
        views.book_caretaker,
        name="book_caretaker",
    ),
    # Manage bookings
    path("my-bookings/", views.my_bookings, name="my_bookings"),
    path("booking/<int:booking_id>/", views.booking_detail, name="booking_detail"),
    path(
        "booking/<int:booking_id>/confirm/",
        views.confirm_booking,
        name="confirm_booking",
    ),
    path(
        "booking/<int:booking_id>/cancel/", views.cancel_booking, name="cancel_booking"
    ),
    path("booking/<int:booking_id>/start/", views.start_booking, name="start_booking"),
    path(
        "booking/<int:booking_id>/complete/",
        views.complete_booking,
        name="complete_booking",
    ),
    # Caretaker availability management
    path(
        "set-availability/", views.caretaker_set_availability, name="set_availability"
    ),
    path(
        "my-availability/", views.caretaker_availability_list, name="availability_list"
    ),
    path(
        "availability/<int:availability_id>/delete/",
        views.delete_availability,
        name="delete_availability",
    ),
]
