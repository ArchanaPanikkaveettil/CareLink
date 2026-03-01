from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from datetime import timedelta  # Import timedelta from datetime

User = get_user_model()

class CareRequest(models.Model):
    CARE_TYPES = [
        ('full_time', 'Full Time'),
        ('part_time', ' Part Time'),
        ('night_care', 'Night Care'),
        ('home_visit', 'Home Visit'),
        ('emergency', 'Emergency Care'),
        ('respite', 'Respite Care'),
        ('palliative', 'Palliative Care'),
        ('post_surgery', 'Post-Surgery Care'),
    ]
    
    GENDER_PREFERENCES = [
        ('any', 'Any'),
        ('female', 'Female'),
        ('male', 'Male'),
    ]
    
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('open', 'Open'),
        ('under_review', 'Under Review'),
        ('interviewing', 'Interviewing'),
        ('assigned', 'Assigned'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('closed', 'Closed'),
    ]
    
    URGENCY_LEVELS = [
        ('low', 'Low - Can wait'),
        ('medium', 'Medium - Within a week'),
        ('high', 'High - Within 2-3 days'),
        ('urgent', 'Urgent - Immediately'),
    ]
    
    PAYMENT_FREQUENCY = [
        ('hourly', 'Per Hour'),
        ('daily', 'Per Day'),
        ('weekly', 'Per Week'),
        ('monthly', 'Per Month'),
    ]
    
    # Basic Information
    request_id = models.CharField(max_length=20, unique=True, editable=False)
    family = models.ForeignKey(User, on_delete=models.CASCADE, related_name='care_requests')
    
    # Patient Information
    patient_name = models.CharField(max_length=100)
    patient_age = models.IntegerField(validators=[MinValueValidator(0), MaxValueValidator(120)])
    patient_gender = models.CharField(max_length=10, choices=[('male', 'Male'), ('female', 'Female'), ('other', 'Other')])
    medical_condition = models.TextField()
    
    # Detailed Medical Information
    mobility_status = models.CharField(max_length=50, choices=[
        ('independent', 'Independent'),
        ('walker', 'Walker/Cane'),
        ('wheelchair', 'Wheelchair'),
        ('bedridden', 'Bedridden'),
    ], default='independent')
    
    cognitive_status = models.CharField(max_length=50, choices=[
        ('normal', 'Normal'),
        ('mild_impairment', 'Mild Cognitive Impairment'),
        ('dementia', 'Dementia'),
        ('alzheimers', 'Alzheimer\'s'),
    ], default='normal')
    
    # Care Requirements
    care_type = models.CharField(max_length=50, choices=CARE_TYPES)
    urgency_level = models.CharField(max_length=20, choices=URGENCY_LEVELS, default='medium')
    
    # Required Skills
    required_skills = models.TextField(help_text="Comma-separated list of required skills")
    preferred_qualifications = models.TextField(blank=True)
    
    # Compensation
    salary_offered = models.DecimalField(max_digits=10, decimal_places=2)
    payment_frequency = models.CharField(max_length=20, choices=PAYMENT_FREQUENCY, default='monthly')
    negotiable = models.BooleanField(default=True)
    
    # Schedule
    shift_timing = models.CharField(max_length=100)
    start_date = models.DateField()
    duration_days = models.IntegerField(help_text="Number of days care is needed")
    end_date = models.DateField(null=True, blank=True)
    
    # Working Hours
    hours_per_day = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    days_per_week = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(7)], default=7)
    
    # Preferences
    gender_preference = models.CharField(max_length=20, choices=GENDER_PREFERENCES, default='any')
    age_preference_min = models.IntegerField(null=True, blank=True)
    age_preference_max = models.IntegerField(null=True, blank=True)
    language_preference = models.CharField(max_length=100, blank=True)
    
    # Location Details
    address = models.TextField()
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    pincode = models.CharField(max_length=10)
    landmark = models.CharField(max_length=200, blank=True)
    
    # Additional Requirements
    special_requirements = models.TextField(blank=True)
    equipment_provided = models.TextField(blank=True, help_text="Medical equipment provided by family")
    
    # Accommodation
    accommodation_provided = models.BooleanField(default=False)
    accommodation_details = models.TextField(blank=True)
    
    # Interview Process
    interview_required = models.BooleanField(default=True)
    interview_type = models.CharField(max_length=20, choices=[
        ('in_person', 'In Person'),
        ('video', 'Video Call'),
        ('phone', 'Phone Call'),
    ], default='video')
    
    # Assigned Caretaker
    assigned_caretaker = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_requests'
    )
    assigned_date = models.DateTimeField(null=True, blank=True)
    
    # Status and Tracking
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    views_count = models.IntegerField(default=0)
    applications_count = models.IntegerField(default=0)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    published_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    
    # Admin Notes
    admin_notes = models.TextField(blank=True)
    flagged = models.BooleanField(default=False)
    flag_reason = models.TextField(blank=True)
    
    def save(self, *args, **kwargs):
        if not self.request_id:
            # Generate unique request ID
            last_request = CareRequest.objects.order_by('-id').first()
            if last_request and last_request.request_id:
                try:
                    last_id = int(last_request.request_id.split('-')[-1])
                    new_id = last_id + 1
                except (ValueError, IndexError):
                    new_id = 1000
            else:
                new_id = 1000
            self.request_id = f"REQ-{timezone.now().strftime('%Y%m')}-{new_id}"
        
        # Calculate end_date from start_date and duration_days
        if self.start_date and self.duration_days is not None:
            try:
                # Ensure duration_days is an integer
                if not isinstance(self.duration_days, int):
                    self.duration_days = int(self.duration_days)
                
                # Use datetime.timedelta (not timezone.timedelta) for date arithmetic
                from datetime import timedelta
                self.end_date = self.start_date + timedelta(days=self.duration_days)
            except (ValueError, TypeError) as e:
                # Log error but don't crash
                print(f"Error calculating end_date: {e}")
                self.end_date = None
        
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.request_id} - {self.patient_name}"
    
    def publish(self):
        """Publish the request (make it open)"""
        self.status = 'open'
        self.published_at = timezone.now()
        self.save()
    
    def close(self):
        """Close the request"""
        self.status = 'closed'
        self.closed_at = timezone.now()
        self.save()
    
    def assign_caretaker(self, caretaker):
        """Assign a caretaker to this request"""
        self.assigned_caretaker = caretaker
        self.assigned_date = timezone.now()
        self.status = 'assigned'
        self.save()
    
    def increment_views(self):
        """Increment view count"""
        self.views_count += 1
        self.save(update_fields=['views_count'])
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Care Request'
        verbose_name_plural = 'Care Requests'


class CareRequestDocument(models.Model):
    """Additional documents for care requests"""
    request = models.ForeignKey(CareRequest, on_delete=models.CASCADE, related_name='documents')
    document = models.FileField(upload_to='request_docs/')
    description = models.CharField(max_length=200)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Document for {self.request.request_id}"


class CareRequestSchedule(models.Model):
    """Detailed schedule for recurring care"""
    request = models.ForeignKey(CareRequest, on_delete=models.CASCADE, related_name='schedules')
    day_of_week = models.IntegerField(choices=[(0, 'Monday'), (1, 'Tuesday'), (2, 'Wednesday'), 
                                               (3, 'Thursday'), (4, 'Friday'), (5, 'Saturday'), (6, 'Sunday')])
    start_time = models.TimeField()
    end_time = models.TimeField()
    
    class Meta:
        unique_together = ['request', 'day_of_week']