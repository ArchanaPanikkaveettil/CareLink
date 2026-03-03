from django.urls import path, include
from . import views

# In apps/Requests/urls.py
urlpatterns = [
    # Family URLs
    path('post/', views.post_request, name='post_request'),
    path('my-requests/', views.my_requests, name='my_requests'),
    path('<int:request_id>/', views.request_detail, name='request_detail'),
    path('<int:request_id>/edit/', views.edit_request, name='edit_request'),
    path('publish/<int:request_id>/', views.publish_request, name='publish_request'),
    
    # Application URL
    path('<int:request_id>/apply/', views.apply_for_request, name='apply_for_request'),
    
    # Edit/Update URLs
    path('<int:request_id>/edit/', views.edit_request, name='edit_request'),
    path('<int:request_id>/close/', views.close_request, name='close_request'),
    path('<int:request_id>/delete/', views.delete_request, name='delete_request'),
    path('<int:request_id>/save-draft/', views.save_draft, name='save_draft'),  # Add this line
    
    # Caretaker URLs
    path('browse/', views.browse_requests, name='browse_requests'),
]