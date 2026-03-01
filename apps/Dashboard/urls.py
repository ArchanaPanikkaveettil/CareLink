from django.urls import path
from . import views

urlpatterns = [
    path('family/dashboard/', views.family_dashboard, name='family_dashboard'),
    path('caretaker/dashboard/', views.caretaker_dashboard,  name='caretaker_dashboard'),
]