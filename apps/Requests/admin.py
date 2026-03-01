from django.contrib import admin
from .models import CareRequest

@admin.register(CareRequest)
class CareRequestAdmin(admin.ModelAdmin):
    list_display = (
        'patient_name',
        'family',
        'care_type',           # Changed from 'service_type' to 'care_type'
        'address',              # Changed from 'location' to 'address'
        'start_date',
        'status',
        'created_at',
    )

    list_filter = (
        'status',
        'care_type',            # Changed from 'service_type' to 'care_type'
        'gender_preference',
        'created_at',
    )

    search_fields = (
        'patient_name',
        'family__username',
        'address',              # Changed from 'location' to 'address'
        'medical_condition',
    )

    readonly_fields = ('created_at', 'updated_at')

    fieldsets = (
        ('Patient Information', {
            'fields': ('patient_name', 'patient_age', 'medical_condition')
        }),
        ('Care Details', {
            'fields': ('care_type', 'salary_offered', 'shift_timing', 
                      'gender_preference', 'special_requirements')
        }),
        ('Location & Schedule', {
            'fields': ('address', 'start_date', 'duration_days')
        }),
        ('Status', {
            'fields': ('status', 'family', 'created_at', 'updated_at')
        }),
    )

    ordering = ('-created_at',)