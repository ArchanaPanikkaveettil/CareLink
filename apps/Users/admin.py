from django.contrib import admin
from django.contrib.auth import get_user_model
from .models import CaretakerProfile, FamilyProfile

User = get_user_model()

admin.site.register(User)
admin.site.register(CaretakerProfile)
admin.site.register(FamilyProfile)