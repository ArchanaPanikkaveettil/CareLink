from django.urls import path
from . import views

app_name = 'assignments'

urlpatterns = [
    # Assignment management
    path('create/<int:application_id>/', views.create_assignment, name='create_assignment'),
    path('family/', views.family_assignments, name='family_assignments'),
    path('caretaker/', views.caretaker_assignments, name='caretaker_assignments'),
    path('family/<int:assignment_id>/', views.family_assignment_detail, name='family_assignment_detail'),
    path('caretaker/<int:assignment_id>/', views.caretaker_assignment_detail, name='caretaker_assignment_detail'),
    path('<int:assignment_id>/terminate/', views.terminate_assignment, name='terminate_assignment'),
    
    # Daily reports
    path('<int:assignment_id>/report/create/', views.create_daily_report, name='create_daily_report'),
    path('<int:assignment_id>/reports/', views.view_reports, name='view_reports'),
    path('report/<int:report_id>/', views.report_detail, name='report_detail'),
    path('report/<int:report_id>/add-notes/', views.add_family_notes, name='add_family_notes'),
    
    # Tasks
    path('<int:assignment_id>/task/create/', views.create_task, name='create_task'),
    path('task/<int:task_id>/update/', views.update_task_status, name='update_task_status'),
    path('<int:assignment_id>/tasks/', views.task_list, name='task_list'),
    path('task/<int:task_id>/', views.task_detail, name='task_detail'),
    
    # Notes
    path('<int:assignment_id>/note/create/', views.create_note, name='create_note'),
    path('<int:assignment_id>/notes/', views.note_list, name='note_list'),
    path('note/<int:note_id>/', views.note_detail, name='note_detail'),
    
    # Attendance
    path('<int:assignment_id>/attendance/mark/', views.mark_attendance, name='mark_attendance'),
    path('<int:assignment_id>/attendance/view/', views.view_attendance, name='view_attendance'),
    path('<int:assignment_id>/attendance/calendar/', views.attendance_calendar, name='attendance_calendar'),
    
    # Salary
    path('<int:assignment_id>/salary/', views.manage_salary, name='manage_salary'),
    path('<int:assignment_id>/salary/process/', views.process_salary, name='process_salary'),
    path('salary/<int:payment_id>/paid/', views.mark_salary_paid, name='mark_salary_paid'),
    path('<int:assignment_id>/salary/history/', views.salary_history, name='salary_history'),
    
    # API endpoints
    path('api/<int:assignment_id>/tasks/', views.get_tasks_api, name='get_tasks_api'),
    path('api/<int:assignment_id>/attendance/', views.get_attendance_api, name='get_attendance_api'),
]