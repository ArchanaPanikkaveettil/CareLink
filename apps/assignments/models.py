from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta, date
from decimal import Decimal

from CareLink import settings

User = get_user_model()


class CareAssignment(models.Model):
    """Model for tracking care assignments between families and caretakers"""
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('terminated', 'Terminated'),
        ('on_hold', 'On Hold'),
    ]
    
    SHIFT_CHOICES = [
        ('full_time', 'Full Time (8 hours)'),
        ('part_time', 'Part Time (4 hours)'),
        ('live_in', 'Live-in (24 hours)'),
        ('hourly', 'Hourly'),
    ]
    
    # Relationships
    family = models.ForeignKey(User, on_delete=models.CASCADE, related_name='assignments_as_family')
    caretaker = models.ForeignKey(User, on_delete=models.CASCADE, related_name='assignments_as_caretaker')
    care_request = models.ForeignKey('Requests.CareRequest', on_delete=models.SET_NULL, null=True, blank=True)
    application = models.ForeignKey('Applications.CareApplication', on_delete=models.SET_NULL, null=True, blank=True)
    
    # Assignment Details
    assigned_date = models.DateTimeField(default=timezone.now)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    
    # Work Details
    shift_type = models.CharField(max_length=20, choices=SHIFT_CHOICES, default='full_time')
    work_hours_per_day = models.DecimalField(max_digits=4, decimal_places=2, default=8.0)
    hourly_rate = models.DecimalField(max_digits=10, decimal_places=2, default=100.00)
    monthly_salary = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    termination_reason = models.TextField(blank=True)
    termination_date = models.DateField(null=True, blank=True)
    
    # Documents
    contract_file = models.FileField(upload_to='assignments/contracts/', blank=True, null=True)
    notes = models.TextField(blank=True)  # This is a TextField for assignment notes
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-assigned_date']
        
    def __str__(self):
        return f"{self.caretaker.get_full_name()} → {self.family.get_full_name()} ({self.get_status_display()})"
    
    def get_current_attendance_summary(self):
        """Get attendance summary for current month"""
        today = date.today()
        start_of_month = today.replace(day=1)
        
        attendances = self.attendance_records.filter(
            date__gte=start_of_month,
            date__lte=today
        )
        
        total_days = attendances.count()
        present_days = attendances.filter(status='present').count()
        absent_days = attendances.filter(status='absent').count()
        late_days = attendances.filter(status='late').count()
        leave_days = attendances.filter(status='leave').count()
        
        return {
            'total_days': total_days,
            'present_days': present_days,
            'absent_days': absent_days,
            'late_days': late_days,
            'leave_days': leave_days,
            'attendance_percentage': (present_days / total_days * 100) if total_days > 0 else 0
        }
    
    def calculate_salary_for_period(self, start_date, end_date):
        """Calculate salary for a given period"""
        attendances = self.attendance_records.filter(
            date__gte=start_date,
            date__lte=end_date,
            status='present'
        )
        
        work_days = attendances.count()
        
        if self.monthly_salary:
            return (self.monthly_salary / 30) * work_days
        else:
            return self.hourly_rate * self.work_hours_per_day * work_days
    
    def get_total_earned_salary(self):
        """Get total salary earned since assignment started"""
        payments = self.salary_payments.filter(status='paid')
        total = payments.aggregate(total=models.Sum('total_amount'))['total'] or 0
        return total


class DailyCareReport(models.Model):
    """Daily care report from caretaker to family"""
    
    MOOD_CHOICES = [
        ('happy', '😊 Happy'),
        ('calm', '😌 Calm'),
        ('sad', '😔 Sad'),
        ('anxious', '😰 Anxious'),
        ('irritable', '😤 Irritable'),
        ('tired', '😴 Tired'),
        ('pain', '😖 In Pain'),
    ]
    
    assignment = models.ForeignKey(CareAssignment, on_delete=models.CASCADE, related_name='daily_reports')
    
    # Report Details
    report_date = models.DateField(default=date.today)
    
    # Vital Signs
    blood_pressure_systolic = models.IntegerField(null=True, blank=True, help_text="Systolic (top number)")
    blood_pressure_diastolic = models.IntegerField(null=True, blank=True, help_text="Diastolic (bottom number)")
    heart_rate = models.IntegerField(null=True, blank=True, help_text="Beats per minute")
    temperature = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True, help_text="°C")
    blood_sugar = models.IntegerField(null=True, blank=True, help_text="mg/dL")
    oxygen_saturation = models.IntegerField(null=True, blank=True, help_text="SpO2 %")
    weight = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, help_text="kg")
    
    # Activities of Daily Living
    meals_taken = models.TextField(blank=True, help_text="What meals were taken and how much")
    water_intake = models.CharField(max_length=50, blank=True, help_text="e.g., 2 liters")
    sleep_hours = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True)
    sleep_quality = models.CharField(max_length=20, blank=True, choices=[
        ('excellent', 'Excellent'),
        ('good', 'Good'),
        ('fair', 'Fair'),
        ('poor', 'Poor'),
    ])
    mood = models.CharField(max_length=20, choices=MOOD_CHOICES, blank=True)
    
    # Care Activities
    medications_given = models.TextField(blank=True, help_text="List medications with time and dosage")
    exercises_done = models.TextField(blank=True, help_text="Exercises performed and duration")
    activities_done = models.TextField(blank=True, help_text="Activities done with patient")
    
    # Observations
    observations = models.TextField(blank=True, help_text="Any notable observations about patient's condition")
    concerns = models.TextField(blank=True, help_text="Any concerns that need attention")
    recommendations = models.TextField(blank=True, help_text="Recommendations for care or follow-up")
    
    # Media
    photo = models.ImageField(upload_to='daily_reports/photos/%Y/%m/%d/', blank=True, null=True)
    
    # Status
    family_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    family_notes = models.TextField(blank=True, help_text="Family response/notes")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-report_date']
        unique_together = ['assignment', 'report_date']
        
    def __str__(self):
        return f"Report for {self.assignment} - {self.report_date}"
    
    @property
    def blood_pressure(self):
        if self.blood_pressure_systolic and self.blood_pressure_diastolic:
            return f"{self.blood_pressure_systolic}/{self.blood_pressure_diastolic}"
        return ""
    
    @property
    def is_abnormal_vitals(self):
        """Check if vitals are outside normal ranges"""
        if self.blood_pressure_systolic and self.blood_pressure_systolic > 140:
            return True
        if self.blood_pressure_diastolic and self.blood_pressure_diastolic > 90:
            return True
        if self.heart_rate and (self.heart_rate < 60 or self.heart_rate > 100):
            return True
        if self.temperature and (self.temperature < 36.1 or self.temperature > 37.2):
            return True
        if self.oxygen_saturation and self.oxygen_saturation < 95:
            return True
        return False


class CareTask(models.Model):
    """Tasks assigned by family to caretaker"""
    
    PRIORITY_CHOICES = [
        ('high', '🔴 High'),
        ('medium', '🟡 Medium'),
        ('low', '🟢 Low'),
    ]
    
    STATUS_CHOICES = [
        ('pending', '⏳ Pending'),
        ('in_progress', '🔄 In Progress'),
        ('completed', '✅ Completed (Action Required)'),
        ('verified', '🛡️ Verified'),
        ('cancelled', '❌ Cancelled'),
    ]
    
    assignment = models.ForeignKey(CareAssignment, on_delete=models.CASCADE, related_name='tasks')
    
    # Task Details
    title = models.CharField(max_length=200)
    description = models.TextField()
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='medium')
    
    # Schedule
    due_date = models.DateTimeField()
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    assigned_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='assigned_tasks')
    
    # Proof of Work
    proof_image = models.ImageField(upload_to='tasks/proof/%Y/%m/%d/', blank=True, null=True)
    
    # Escalation & Notifications
    escalation_level = models.IntegerField(default=0, help_text="0: None, 1: Nurse, 2: Family, 3: Admin")
    missed_notification_sent = models.BooleanField(default=False)
    
    # Notes
    caretaker_notes = models.TextField(blank=True)
    family_feedback = models.TextField(blank=True)
    
    # Reminders
    reminder_sent = models.BooleanField(default=False)
    reminder_sent_at = models.DateTimeField(null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-priority', 'due_date']
        
    def __str__(self):
        return f"{self.title} - {self.assignment.caretaker.get_full_name()}"
    
    def is_overdue(self):
        return self.due_date < timezone.now() and self.status not in ['completed', 'cancelled']
    
    def get_time_remaining(self):
        if self.status in ['completed', 'cancelled']:
            return None
        remaining = self.due_date - timezone.now()
        if remaining.total_seconds() < 0:
            return "Overdue"
        days = remaining.days
        hours = remaining.seconds // 3600
        if days > 0:
            return f"{days} day(s) left"
        elif hours > 0:
            return f"{hours} hour(s) left"
        else:
            return "Due soon"


class CareNote(models.Model):
    """Professional notes shared between family and caretaker"""
    
    NOTE_TYPES = [
        ('medical', '🏥 Medical'),
        ('routine', '📋 Routine'),
        ('emergency', '🚨 Emergency'),
        ('general', '📝 General'),
        ('feedback', '💬 Feedback'),
        ('reminder', '⏰ Reminder'),
    ]
    
    # FIXED: Changed related_name to avoid conflict with CareAssignment.notes field
    assignment = models.ForeignKey(CareAssignment, on_delete=models.CASCADE, related_name='care_notes')
    
    # Note Details
    title = models.CharField(max_length=200)
    content = models.TextField()
    note_type = models.CharField(max_length=20, choices=NOTE_TYPES, default='general')
    
    # Author
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_notes')
    
    # Read Status
    read_by_family = models.BooleanField(default=False)
    read_by_caretaker = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    
    # Importance
    is_important = models.BooleanField(default=False)
    is_urgent = models.BooleanField(default=False)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-is_urgent', '-is_important', '-created_at']
        
    def __str__(self):
        return f"{self.title} - {self.created_by.get_full_name()}"
    
    def is_read_by(self, user):
        if user.role == 'family':
            return self.read_by_family
        else:
            return self.read_by_caretaker
    
    def mark_read(self, user):
        if user.role == 'family':
            self.read_by_family = True
        else:
            self.read_by_caretaker = True
        self.read_at = timezone.now()
        self.save()


class Attendance(models.Model):
    """Daily attendance tracking for caretakers"""
    
    STATUS_CHOICES = [
        ('present', '✅ Present'),
        ('absent', '❌ Absent'),
        ('late', '⏰ Late'),
        ('leave', '🏖️ Leave'),
        ('holiday', '🎉 Holiday'),
    ]
    
    assignment = models.ForeignKey(CareAssignment, on_delete=models.CASCADE, related_name='attendance_records')
    
    # Attendance Details
    date = models.DateField(default=date.today)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='present')
    
    # Time Tracking
    check_in_time = models.TimeField(null=True, blank=True)
    check_out_time = models.TimeField(null=True, blank=True)
    late_minutes = models.IntegerField(default=0)
    early_leave_minutes = models.IntegerField(default=0)
    
    # Work Hours
    actual_hours_worked = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    overtime_hours = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    # Notes
    notes = models.TextField(blank=True)
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_attendance')
    approved_at = models.DateTimeField(null=True, blank=True)
    
    # Location
    check_in_location = models.CharField(max_length=255, blank=True)
    check_out_location = models.CharField(max_length=255, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['assignment', 'date']
        ordering = ['-date']
        
    def __str__(self):
        return f"{self.assignment.caretaker.get_full_name()} - {self.date}: {self.get_status_display()}"
    
    def calculate_work_hours(self):
        """Calculate actual work hours from check-in/out times"""
        if self.check_in_time and self.check_out_time:
            from datetime import datetime
            check_in = datetime.combine(self.date, self.check_in_time)
            check_out = datetime.combine(self.date, self.check_out_time)
            diff = check_out - check_in
            hours = diff.total_seconds() / 3600
            
            standard_hours = float(self.assignment.work_hours_per_day)
            if hours > standard_hours:
                self.overtime_hours = hours - standard_hours
                self.actual_hours_worked = standard_hours
            else:
                self.actual_hours_worked = hours
                self.overtime_hours = 0
            
            if self.assignment.application and self.assignment.application.work_start_time:
                expected_start_time = self.assignment.application.work_start_time
            else:
                expected_start_time = datetime.strptime("09:00", "%H:%M").time()
            expected_check_in = datetime.combine(self.date, expected_start_time)
            if check_in > expected_check_in:
                self.late_minutes = int((check_in - expected_check_in).total_seconds() / 60)
            
            self.save()
            return self.actual_hours_worked
        return 0


class SalaryPayment(models.Model):
    """Salary payment records for caretakers"""
    
    PAYMENT_STATUS = [
        ('pending', '⏳ Pending'),
        ('processed', '🔄 Processed'),
        ('paid', '✅ Paid'),
        ('failed', '❌ Failed'),
    ]
    
    PAYMENT_METHODS = [
        ('bank_transfer', '🏦 Bank Transfer'),
        ('cash', '💵 Cash'),
        ('check', '📝 Check'),
        ('upi', '📱 UPI'),
    ]
    
    assignment = models.ForeignKey(CareAssignment, on_delete=models.CASCADE, related_name='salary_payments')
    
    # Payment Details
    payment_month = models.DateField()
    base_salary = models.DecimalField(max_digits=10, decimal_places=2)
    overtime_pay = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    bonus = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    deductions = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Attendance Summary
    days_worked = models.IntegerField()
    days_present = models.IntegerField()
    days_absent = models.IntegerField()
    days_late = models.IntegerField(default=0)
    days_leave = models.IntegerField(default=0)
    overtime_hours = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    # Payment Info
    status = models.CharField(max_length=20, choices=PAYMENT_STATUS, default='pending')
    payment_date = models.DateTimeField(null=True, blank=True)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS, null=True, blank=True)
    transaction_id = models.CharField(max_length=100, blank=True)
    
    # Notes
    notes = models.TextField(blank=True)
    processed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='processed_payments')
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-payment_month']
        unique_together = ['assignment', 'payment_month']
        
    def __str__(self):
        return f"Salary for {self.assignment.caretaker.get_full_name()} - {self.payment_month.strftime('%B %Y')} - ₹{self.total_amount:,.2f}"
    
    def get_month_name(self):
        return self.payment_month.strftime('%B %Y')


class CaregiverReview(models.Model):
    """Review for caregiver after assignment termination"""
    RATING_CHOICES = [
        (1, '1 Star - Poor'),
        (2, '2 Stars - Fair'),
        (3, '3 Stars - Good'),
        (4, '4 Stars - Very Good'),
        (5, '5 Stars - Excellent'),
    ]
    
    assignment = models.OneToOneField('CareAssignment', on_delete=models.CASCADE, related_name='review')
    caregiver = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='reviews_received')
    family = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='reviews_given')
    rating = models.IntegerField(choices=RATING_CHOICES)
    review_text = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        
    def __str__(self):
        return f"{self.caregiver.get_full_name()} - {self.rating} stars"