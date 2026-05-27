from django.urls import path
from . import views

urlpatterns = [
    path('', views.user_chat, name='user_chat'),
    path('admin/', views.admin_chat_list, name='admin_chat_list'),
    path('admin/<int:session_id>/', views.admin_chat_detail, name='admin_chat_detail'),
    path('send/<int:session_id>/', views.send_message, name='send_message'),
]
