
from django.urls import path
from . import views

urlpatterns = [

    # Home / Landing Page
    path(
        '',
        views.index,
        name='index'
    ),

    # Login
    path(
        'login/',
        views.custom_login,
        name='login'
    ),

    # Registration
    path(
        'register/family/',
        views.family_register,
        name='family_register'
    ),

    path(
        'register/caretaker/',
        views.caretaker_register,
        name='caretaker_register'
    ),

    # Verification page (for unapproved caretakers)
    path(
        'verification-pending/',
        views.verification_pending,
        name='verification_pending'
    ),

    # Search caretakers (Family feature)
    path(
        'search-caretakers/',
        views.search_caretakers,
        name='search_caretakers'
    ),

    # View caretaker details
    path(
        'caretaker/<int:id>/',
        views.caretaker_detail,
        name='caretaker_detail'
    ),
    path('profile/family/', views.family_profile, name='family_profile'),
    path('profile/family/update/', views.update_family_profile, name='update_family_profile'),
     path('profile/caretaker/', views.caretaker_profile, name='caretaker_profile'),
    path('profile/caretaker/update/', views.update_caretaker_profile, name='update_caretaker_profile'),
]