from django.urls import path
from . import views

urlpatterns = [
    path('get/', views.get_notifications, name='get_notifications'),
    path('count/', views.notification_count, name='notification_count'),
    path('mark/<int:notification_id>/', views.mark_notification_read, name='mark_notification_read'),
    path('mark-all/', views.mark_all_notifications_read, name='mark_all_notifications_read'),
    path('all/', views.all_notifications, name='all_notifications'),
]