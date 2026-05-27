#!/usr/bin/env python
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'CareLink.settings')
django.setup()
from django.contrib.auth import get_user_model

User = get_user_model()
admin = User.objects.get(username='admin')
print(f'Admin role: "{admin.role}"')
admin.role = 'admin'
admin.save()
print(f'Updated admin role to: "{admin.role}"')
