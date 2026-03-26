from django.apps import AppConfig


class AssignmentsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.assignments'  # This MUST be 'apps.Assignments', not 'assignments'
    verbose_name = 'Care assignments'