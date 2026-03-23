from django.urls import path
from . import views

app_name = 'applications'

urlpatterns = [
    # ============================================================================
    # CARETAKER URLS
    # ============================================================================
    # Apply for a request
    path('apply/<int:request_id>/', views.apply_request, name='apply_request'),
    
    # View my applications
    path('my-applications/', views.my_applications, name='my_applications'),
    
    # Withdraw application 
    path('withdraw/<int:application_id>/', views.withdraw_application, name='withdraw_application'),
    
    # View full offer details (CARETAKER ONLY)
    path('offer/<int:application_id>/', views.view_offer, name='view_offer'),
    
    # Respond to offer (accept/decline)
    path('respond-offer/<int:application_id>/<str:response>/', views.respond_to_offer, name='respond_to_offer'),

    # ============================================================================
    # FAMILY URLS
    # ============================================================================
    # View all applications
    path('family/', views.family_applications, name='family_applications'),

    # View applications for a specific request
    path('request/<int:request_id>/', views.request_applications, name='request_applications'),
    
    # Shortlist application
    path('shortlist/<int:application_id>/', views.shortlist_application, name='shortlist_application'),
    
    # View shortlisted candidates
    path('shortlisted/<int:request_id>/', views.shortlisted_candidates, name='shortlisted_candidates'),
    
    # Update shortlist rank
    path('shortlist/rank/<int:application_id>/<str:direction>/', 
         views.update_shortlist_rank, 
         name='update_shortlist_rank'),
    
    # Add shortlist notes
    path('shortlist/notes/<int:application_id>/', 
         views.add_shortlist_notes, 
         name='add_shortlist_notes'),
    
    # Remove from shortlist
    path('shortlist/remove/<int:application_id>/', 
         views.remove_shortlist, 
         name='remove_shortlist'),
    
    # Send offer to shortlisted candidate
    path('send-offer/<int:application_id>/', views.send_offer, name='send_offer'),
    
    # Accept application (direct hire)
    path('accept/<int:application_id>/', views.accept_application, name='accept_application'),
    
    # Reject application
    path('reject/<int:application_id>/', views.reject_application, name='reject_application'),

    # ============================================================================
    # SHARED URLS
    # ============================================================================
    # View caretaker public profile
    path('caretaker/<int:user_id>/', 
         views.caretaker_profile_detail, 
         name='caretaker_profile_detail'),
    
    # View application details
    path('detail/<int:application_id>/', views.application_detail, name='application_detail'),
    
    # Mark care as started
    path('mark-started/<int:application_id>/', views.mark_care_started, name='mark_care_started'),
]