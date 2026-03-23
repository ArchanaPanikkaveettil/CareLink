from django.urls import path
from . import views

app_name = 'notifications'

urlpatterns = [
    # View all notifications
    path('', views.all_notifications, name='all_notifications'),
    
    # AJAX endpoints
    path('get/', views.get_notifications_ajax, name='get_notifications'),
    path('count/', views.get_notification_count, name='notification_count'),
    
    # Mark as read
    path('<int:notification_id>/mark-read/', views.mark_notification_read, name='mark_notification_read'),
    path('mark-all-read/', views.mark_all_read, name='mark_all_read'),
    
    # Delete notifications
    path('delete-all/', views.delete_all_notifications, name='delete_all_notifications'),
    path('delete-read/', views.delete_read_notifications, name='delete_read_notifications'),
    path('<int:notification_id>/delete/', views.delete_notification, name='delete_notification'),
]