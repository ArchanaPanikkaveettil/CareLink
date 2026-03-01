from django.apps import AppConfig

class RequestsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.Requests'  # This MUST be 'apps.Requests', not just 'Requests'