# apps/Notifications/urls.py
from django.urls import path
from . import views

app_name = 'notifications'


urlpatterns = [
    path('', views.all_notifications, name='all'),
    path('get/', views.get_notifications_ajax, name='get'),
    path('mark-all-read/', views.mark_all_read, name='mark_all_read'),
    path('<int:notification_id>/mark-read/', views.mark_notification_read, name='mark_read'),
]
