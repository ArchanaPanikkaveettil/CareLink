from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from datetime import timedelta
from django.db import transaction
from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError


User = get_user_model()


class CareRequest(models.Model):
    CARE_TYPES = [
        ("full_time", "Full Time"),
        ("part_time", "Part Time"),
        ("night_care", "Night Care"),
        ("home_visit", "Home Visit"),
        ("emergency", "Emergency Care"),
        ("respite", "Respite Care"),
        ("palliative", "Palliative Care"),
        ("post_surgery", "Post-Surgery Care"),
    ]

    GENDER_PREFERENCES = [
        ("any", "Any"),
        ("female", "Female"),
        ("male", "Male"),
    ]

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("open", "Open"),
        ("under_review", "Under Review"),
        ("interviewing", "Interviewing"),
        ("assigned", "Assigned"),
        ("in_progress", "In Progress"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
        ("closed", "Closed"),
    ]

    URGENCY_LEVELS = [
        ("low", "Low - Can wait"),
        ("medium", "Medium - Within a week"),
        ("high", "High - Within 2-3 days"),
        ("urgent", "Urgent - Immediately"),
    ]

    PAYMENT_FREQUENCY = [
        ("hourly", "Per Hour"),
        ("daily", "Per Day"),
        ("weekly", "Per Week"),
        ("monthly", "Per Month"),
    ]

    # Basic Information
    request_id = models.CharField(max_length=20, unique=True, editable=False)
    family = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="care_requests"
    )

    # Patient Information
    patient_name = models.CharField(max_length=100)
    patient_age = models.IntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(120)]
    )
    patient_gender = models.CharField(
        max_length=10,
        choices=[("male", "Male"), ("female", "Female"), ("other", "Other")],
    )
    medical_condition = models.TextField()

    # Detailed Medical Information
    mobility_status = models.CharField(
        max_length=50,
        choices=[
            ("independent", "Independent"),
            ("walker", "Walker/Cane"),
            ("wheelchair", "Wheelchair"),
            ("bedridden", "Bedridden"),
        ],
        default="independent",
    )

    cognitive_status = models.CharField(
        max_length=50,
        choices=[
            ("normal", "Normal"),
            ("mild_impairment", "Mild Cognitive Impairment"),
            ("dementia", "Dementia"),
            ("alzheimers", "Alzheimer's"),
        ],
        default="normal",
    )

    # Care Requirements
    care_type = models.CharField(max_length=50, choices=CARE_TYPES)
    urgency_level = models.CharField(
        max_length=20, choices=URGENCY_LEVELS, default="medium"
    )

    # Required Skills
    required_skills = models.TextField(
        help_text="Comma-separated list of required skills"
    )
    preferred_qualifications = models.TextField(blank=True)

    # Compensation
    salary_offered = models.DecimalField(max_digits=10, decimal_places=2)
    payment_frequency = models.CharField(
        max_length=20, choices=PAYMENT_FREQUENCY, default="monthly"
    )
    negotiable = models.BooleanField(default=True)

    # Schedule
    shift_timing = models.CharField(max_length=100)
    start_date = models.DateField()
    duration_days = models.IntegerField(help_text="Number of days care is needed")
    end_date = models.DateField(null=True, blank=True)

    # Working Hours
    hours_per_day = models.DecimalField(
        max_digits=4, decimal_places=2, null=True, blank=True
    )
    days_per_week = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(7)], default=7
    )

    # Preferences
    gender_preference = models.CharField(
        max_length=20, choices=GENDER_PREFERENCES, default="any"
    )
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
    equipment_provided = models.TextField(
        blank=True, help_text="Medical equipment provided by family"
    )

    # Accommodation
    accommodation_provided = models.BooleanField(default=False)
    accommodation_details = models.TextField(blank=True)

    # Interview Process
    interview_required = models.BooleanField(default=True)
    interview_type = models.CharField(
        max_length=20,
        choices=[
            ("in_person", "In Person"),
            ("video", "Video Call"),
            ("phone", "Phone Call"),
        ],
        default="video",
    )

    # Emergency Contact Information
    emergency_contact_name = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Emergency contact person's name",
    )
    emergency_contact_phone = models.CharField(
        max_length=20, blank=True, null=True, help_text="Emergency contact phone number"
    )

    # Care Details (for detailed requirements)
    care_details = models.TextField(
        blank=True, null=True, help_text="Detailed description of care requirements"
    )

    # Assigned Caretaker
    assigned_caretaker = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_requests",
    )
    assigned_date = models.DateTimeField(null=True, blank=True)

    # Status and Tracking
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
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
            last_request = CareRequest.objects.order_by("-id").first()
            if last_request and last_request.request_id:
                try:
                    last_id = int(last_request.request_id.split("-")[-1])
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

                # Use datetime.timedelta for date arithmetic
                from datetime import timedelta

                self.end_date = self.start_date + timedelta(days=self.duration_days)
            except (ValueError, TypeError) as e:
                # Log error but don't crash
                print(f"Error calculating end_date: {e}")
                self.end_date = None

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.request_id} - {self.patient_name}"

    # ============================================================================
    # STATUS CHECK METHODS
    # ============================================================================

    def can_edit(self):
        """Check if request can be edited - Only drafts can be edited"""
        return self.status == "draft"

    def can_publish(self):
        """Check if request can be published - Only drafts can be published"""
        return self.status == "draft"

    def can_apply(self):
        """Check if caretakers can apply - Only open requests with no assigned caretaker"""
        return self.status == "open" and not self.assigned_caretaker

    def can_send_offer(self):
        """Check if offers can be sent - Only open requests with no assigned caretaker"""
        return self.status == "open" and not self.assigned_caretaker

    def can_close(self):
        """Check if request can be closed - Open or assigned requests can be closed"""
        return self.status in ["open", "assigned", "in_progress"]

    def can_reopen(self):
        """Check if closed request can be reopened - Only if no caretaker was assigned"""
        return self.status == "closed" and not self.assigned_caretaker

    def is_active(self):
        """Check if request is active (accepting applications)"""
        return self.status == "open" and not self.assigned_caretaker

    def is_assigned(self):
        """Check if request has an assigned caretaker"""
        return self.assigned_caretaker is not None and self.status in [
            "assigned",
            "in_progress",
        ]

    # ============================================================================
    # ACTION METHODS
    # ============================================================================

    def publish(self):
        """Publish the request (make it open)"""
        if not self.can_publish():
            raise ValueError("Only draft requests can be published.")
        self.status = "open"
        self.published_at = timezone.now()
        self.save()
        return True

    def close(self):
        """Close the request"""
        if not self.can_close():
            raise ValueError(f"Cannot close a request with status: {self.status}")

        from apps.Applications.models import CareApplication

        with transaction.atomic():
            self.status = "closed"
            self.closed_at = timezone.now()
            self.save()

            # Reject all pending applications
            CareApplication.objects.filter(request=self, status="pending").update(
                status="rejected", rejection_note="Request closed by family"
            )
        return True

    def reopen(self):
        """Reopen a closed request"""
        if not self.can_reopen():
            raise ValueError(
                "Cannot reopen a request that has an assigned caretaker or is not closed."
            )
        self.status = "open"
        self.closed_at = None
        self.save()
        return True

    def assign_caretaker(self, caretaker):
        """Assign a caretaker to this request"""
        if self.assigned_caretaker:
            raise ValueError("This request already has an assigned caretaker.")

        if self.status not in ["open", "assigned"]:
            raise ValueError(
                f"Cannot assign caretaker to request with status: {self.status}"
            )

        from apps.Applications.models import CareApplication

        with transaction.atomic():
            self.assigned_caretaker = caretaker
            self.assigned_date = timezone.now()
            self.status = "assigned"
            self.save()

            # Reject all other applications
            CareApplication.objects.filter(request=self).exclude(
                caretaker=caretaker
            ).update(status="rejected")
        return True

    def start_care(self):
        """Mark care as started"""
        if self.status != "assigned":
            raise ValueError(
                f"Cannot start care for request with status: {self.status}"
            )
        if not self.assigned_caretaker:
            raise ValueError("Cannot start care without an assigned caretaker")

        self.status = "in_progress"
        self.save()
        return True

    def complete_care(self):
        """Mark care as completed"""
        if self.status != "in_progress":
            raise ValueError(
                f"Cannot complete care for request with status: {self.status}"
            )

        self.status = "completed"
        self.save()
        return True

    def increment_views(self):
        """Increment view count"""
        self.views_count += 1
        self.save(update_fields=["views_count"])

    # ============================================================================
    # UTILITY METHODS
    # ============================================================================

    def get_applications_count(self):
        """Get total number of applications"""
        from apps.Applications.models import CareApplication

        return CareApplication.objects.filter(request=self).count()

    def get_pending_applications_count(self):
        """Get number of pending applications"""
        from apps.Applications.models import CareApplication

        return CareApplication.objects.filter(request=self, status="pending").count()

    def get_shortlisted_count(self):
        """Get number of shortlisted candidates"""
        from apps.Applications.models import CareApplication

        return CareApplication.objects.filter(
            request=self, status="shortlisted"
        ).count()

    def get_offers_sent_count(self):
        """Get number of offers sent"""
        from apps.Applications.models import CareApplication

        return CareApplication.objects.filter(
            request=self, status__in=["offer_sent", "offer_accepted", "offer_declined"]
        ).count()

    def has_active_shortlist(self):
        """Check if request has active shortlisted candidates"""
        from apps.Applications.models import CareApplication

        return CareApplication.objects.filter(
            request=self, status="shortlisted"
        ).exists()

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Care Request"
        verbose_name_plural = "Care Requests"


class CareRequestSchedule(models.Model):
    """Detailed schedule for recurring care"""

    request = models.ForeignKey(
        CareRequest, on_delete=models.CASCADE, related_name="schedules"
    )
    day_of_week = models.IntegerField(
        choices=[
            (0, "Monday"),
            (1, "Tuesday"),
            (2, "Wednesday"),
            (3, "Thursday"),
            (4, "Friday"),
            (5, "Saturday"),
            (6, "Sunday"),
        ]
    )
    start_time = models.TimeField()
    end_time = models.TimeField()

    class Meta:
        unique_together = ["request", "day_of_week"]

        # Add these imports at the top if not already present




# Add these models to your existing models.py file (after your existing CareRequest model)


class CaretakerAvailability(models.Model):
    """Availability schedule for caretakers"""

    caretaker = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="availabilities",
    )

    # Date and time
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()

    # Status
    STATUS_CHOICES = [
        ("available", "Available"),
        ("booked", "Booked"),
        ("unavailable", "Unavailable"),
    ]
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="available"
    )

    # Reference to booking if booked
    booked_request = models.ForeignKey(
        "CareRequest",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="booked_slots",
    )

    # Recurring pattern
    is_recurring = models.BooleanField(default=False)
    recurring_until = models.DateField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ["caretaker", "date", "start_time"]
        ordering = ["date", "start_time"]
        indexes = [
            models.Index(fields=["caretaker", "date", "status"]),
        ]

    def __str__(self):
        return f"{self.caretaker.get_full_name()} - {self.date} {self.start_time}-{self.end_time}"

    def clean(self):
        """Validate time slots"""
        if self.end_time <= self.start_time:
            raise ValidationError("End time must be after start time")

        if self.date < timezone.now().date():
            raise ValidationError("Cannot set availability for past dates")

    def is_available_for_booking(self, start_time, end_time, date):
        """Check if this availability slot can accommodate a booking"""
        if self.status != "available":
            return False, "Slot is not available"

        if self.date != date:
            return False, "Date mismatch"

        # Check if the requested time fits within the availability slot
        if start_time < self.start_time or end_time > self.end_time:
            return False, "Requested time outside available hours"

        return True, "Slot available"


class CareBooking(models.Model):
    """Booking record when family books a caretaker"""

    BOOKING_STATUS = [
        ("pending", "Pending"),
        ("confirmed", "Confirmed"),
        ("in_progress", "In Progress"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
        ("no_show", "No Show"),
    ]

    # Related models
    care_request = models.ForeignKey(
        "CareRequest", on_delete=models.CASCADE, related_name="bookings"
    )
    caretaker = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="bookings_as_caretaker",
    )
    family = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="bookings_as_family",
    )

    # Booking details
    booking_date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    duration_hours = models.DecimalField(max_digits=4, decimal_places=1)

    # Status and tracking
    status = models.CharField(max_length=20, choices=BOOKING_STATUS, default="pending")

    # Notes
    family_notes = models.TextField(blank=True)
    caretaker_notes = models.TextField(blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-booking_date", "start_time"]
        unique_together = ["caretaker", "booking_date", "start_time"]
        indexes = [
            models.Index(fields=["caretaker", "booking_date", "status"]),
            models.Index(fields=["care_request", "status"]),
        ]

    def __str__(self):
        return f"Booking: {self.caretaker.get_full_name()} - {self.booking_date}"

    def get_total_amount(self):
        """Calculate total amount for this booking"""
        if self.care_request.salary_offered and self.duration_hours:
            return self.duration_hours * self.care_request.salary_offered
        return None

    def confirm_booking(self):
        """Confirm the booking and update availability"""
        if self.status == "pending":
            self.status = "confirmed"
            self.confirmed_at = timezone.now()
            self.save()

            # Mark the availability slot as booked
            availability = CaretakerAvailability.objects.filter(
                caretaker=self.caretaker,
                date=self.booking_date,
                start_time=self.start_time,
            ).first()

            if availability:
                availability.status = "booked"
                availability.booked_request = self.care_request
                availability.save()

            return True
        return False

    def cancel_booking(self):
        """Cancel the booking and free up the slot"""
        if self.status not in ["completed", "cancelled"]:
            self.status = "cancelled"
            self.cancelled_at = timezone.now()
            self.save()

            # Free up the availability slot
            availability = CaretakerAvailability.objects.filter(
                caretaker=self.caretaker,
                date=self.booking_date,
                start_time=self.start_time,
            ).first()

            if availability:
                availability.status = "available"
                availability.booked_request = None
                availability.save()

            return True
        return False

    def complete_booking(self):
        """Mark booking as completed"""
        if self.status == "in_progress":
            self.status = "completed"
            self.completed_at = timezone.now()
            self.save()
            return True
        return False
