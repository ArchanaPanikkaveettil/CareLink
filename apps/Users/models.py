from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator, MinValueValidator, MaxValueValidator
from django.utils import timezone
import uuid

# Create your models here.

# ---------------------------
# Custom User Model
# ---------------------------


class User(AbstractUser):

    ROLE_CHOICES = (
        ("admin", "Admin"),
        ("family", "Family"),
        ("caretaker", "Caretaker"),
    )

    VERIFICATION_STATUS = (
        ("pending", "Pending Verification"),
        ("verified", "Verified"),
        ("rejected", "Rejected"),
        ("suspended", "Suspended"),
    )

    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    is_verified = models.BooleanField(default=False)
    verification_status = models.CharField(
        max_length=20, choices=VERIFICATION_STATUS, default="pending"
    )
    verification_documents = models.FileField(
        upload_to="verification_docs/", null=True, blank=True
    )

    # Contact Information
    phone_regex = RegexValidator(
        regex=r"^\+?1?\d{9,15}$",
        message="Phone number must be entered in format: '+999999999'. Up to 15 digits allowed.",
    )
    phone = models.CharField(validators=[phone_regex], max_length=17, blank=True)

    # Profile Picture
    profile_picture = models.ImageField(
        upload_to="profile_pics/", null=True, blank=True
    )

    # Email verification
    email_verified = models.BooleanField(default=False)
    email_verification_token = models.UUIDField(default=uuid.uuid4, editable=False)

    # Two-factor authentication
    two_factor_enabled = models.BooleanField(default=False)
    two_factor_secret = models.CharField(max_length=32, blank=True)

    # Account status
    is_active = models.BooleanField(default=True)
    date_joined = models.DateTimeField(default=timezone.now)
    last_login_ip = models.GenericIPAddressField(null=True, blank=True)

    # Privacy settings
    show_phone = models.BooleanField(default=False)
    show_email = models.BooleanField(default=False)

    # Terms acceptance
    accepted_terms = models.BooleanField(default=False)
    accepted_terms_date = models.DateTimeField(null=True, blank=True)

    # Notification preferences
    email_notifications = models.BooleanField(default=True)
    sms_notifications = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.get_full_name() or self.username} - {self.role}"

    def get_full_name(self):
        return f"{self.first_name} {self.last_name}".strip() or self.username


# ---------------------------
# Elder Profile Model (define BEFORE FamilyProfile)
# ---------------------------


class ElderProfile(models.Model):
    """Model for elderly persons under a family's care"""

    RELATIONSHIP_CHOICES = [
        ("parent", "Parent"),
        ("grandparent", "Grandparent"),
        ("spouse", "Spouse"),
        ("sibling", "Sibling"),
        ("other", "Other"),
    ]

    GENDER_CHOICES = [
        ("male", "Male"),
        ("female", "Female"),
        ("other", "Other"),
    ]

    BLOOD_GROUP_CHOICES = [
        ("A+", "A+"),
        ("A-", "A-"),
        ("B+", "B+"),
        ("B-", "B-"),
        ("O+", "O+"),
        ("O-", "O-"),
        ("AB+", "AB+"),
        ("AB-", "AB-"),
        ("unknown", "Unknown"),
    ]

    MOBILITY_STATUS = [
        ("independent", "Independent"),
        ("walker", "Walker/Cane"),
        ("wheelchair", "Wheelchair"),
        ("bedridden", "Bedridden"),
    ]

    COGNITIVE_STATUS = [
        ("normal", "Normal"),
        ("mild_impairment", "Mild Cognitive Impairment"),
        ("dementia", "Dementia"),
        ("alzheimers", "Alzheimer's"),
    ]

    # Basic Information
    family = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="elder_profiles",
        limit_choices_to={"role": "family"},
    )
    name = models.CharField(max_length=100)
    age = models.IntegerField(validators=[MinValueValidator(0), MaxValueValidator(120)])
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES)
    relationship = models.CharField(
        max_length=20, choices=RELATIONSHIP_CHOICES, default="parent"
    )

    # Medical Information
    blood_group = models.CharField(
        max_length=10, choices=BLOOD_GROUP_CHOICES, blank=True, default=""
    )
    medical_conditions = models.TextField(
        help_text="List of medical conditions", blank=True, default=""
    )
    allergies = models.TextField(blank=True, default="")
    medications = models.TextField(
        help_text="Current medications", blank=True, default=""
    )
    dietary_restrictions = models.TextField(blank=True, default="")

    # Care Requirements
    mobility_status = models.CharField(
        max_length=20, choices=MOBILITY_STATUS, default="independent"
    )
    cognitive_status = models.CharField(
        max_length=20, choices=COGNITIVE_STATUS, default="normal"
    )

    # Emergency Contact (specific to this elder)
    emergency_contact_name = models.CharField(max_length=100, blank=True, default="")
    emergency_contact_phone = models.CharField(max_length=20, blank=True, default="")
    emergency_contact_relation = models.CharField(max_length=50, blank=True, default="")

    # Additional Information
    notes = models.TextField(
        blank=True, default="", help_text="Any additional notes about the elder"
    )
    is_primary = models.BooleanField(
        default=False, help_text="Primary elder for quick requests"
    )

    # Profile Picture (optional)
    profile_picture = models.ImageField(upload_to="elder_pics/", null=True, blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_primary", "name"]
        verbose_name = "Elder Profile"
        verbose_name_plural = "Elder Profiles"

    def __str__(self):
        return f"{self.name} ({self.get_relationship_display()})"

    def save(self, *args, **kwargs):
        # Ensure only one primary elder per family
        if self.is_primary:
            ElderProfile.objects.filter(family=self.family, is_primary=True).exclude(
                id=self.id
            ).update(is_primary=False)
        super().save(*args, **kwargs)

    # ==================== PROPERTIES FOR TEMPLATES ====================

    @property
    def age_display(self):
        """Return age with suffix"""
        if self.age:
            return f"{self.age} years"
        return "Not specified"

    @property
    def medical_info_summary(self):
        """Return summary of medical conditions"""
        if self.medical_conditions:
            return (
                self.medical_conditions[:100] + "..."
                if len(self.medical_conditions) > 100
                else self.medical_conditions
            )
        return "No medical conditions specified"

    @property
    def has_emergency_contact(self):
        """Check if emergency contact exists"""
        return bool(self.emergency_contact_name and self.emergency_contact_phone)

    @property
    def full_emergency_contact(self):
        """Return formatted emergency contact"""
        if self.has_emergency_contact:
            contact = self.emergency_contact_name
            if self.emergency_contact_phone:
                contact += f" - {self.emergency_contact_phone}"
            if self.emergency_contact_relation:
                contact += f" ({self.emergency_contact_relation})"
            return contact
        return "No emergency contact"

    @property
    def mobility_badge_class(self):
        """Return CSS class for mobility status badge"""
        badge_map = {
            "independent": "success",
            "walker": "warning",
            "wheelchair": "info",
            "bedridden": "danger",
        }
        return badge_map.get(self.mobility_status, "secondary")

    @property
    def cognitive_badge_class(self):
        """Return CSS class for cognitive status badge"""
        badge_map = {
            "normal": "success",
            "mild_impairment": "warning",
            "dementia": "danger",
            "alzheimers": "danger",
        }
        return badge_map.get(self.cognitive_status, "secondary")


# ---------------------------
# Caretaker Profile
# ---------------------------


class CaretakerProfile(models.Model):

    AVAILABILITY_CHOICES = [
        ("available", "Available"),
        ("busy", "Busy"),
        ("fully_booked", "Fully Booked"),
        ("offline", "Offline"),
        ("on_leave", "On Leave"),
    ]

    EMPLOYMENT_TYPE = [
        ("full_time", "Full Time"),
        ("part_time", "Part Time"),
        ("freelance", "Freelance"),
        ("contract", "Contract"),
    ]

    EXPERIENCE_LEVEL = [
        ("entry", "Entry Level (0-2 years)"),
        ("mid", "Mid Level (3-5 years)"),
        ("senior", "Senior Level (6-10 years)"),
        ("expert", "Expert (10+ years)"),
    ]

    GENDER_CHOICES = [
        ("male", "Male"),
        ("female", "Female"),
        ("other", "Other"),
        ("prefer_not_to_say", "Prefer Not to Say"),
    ]

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="caretaker_profile"
    )

    # Personal Information
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(
        max_length=20,
        choices=GENDER_CHOICES,
        default="prefer_not_to_say",
        null=True,
        blank=True,
    )

    # Contact Information
    emergency_contact_name = models.CharField(max_length=100, blank=True, default="")
    emergency_contact_phone = models.CharField(max_length=15, blank=True, default="")
    emergency_contact_relation = models.CharField(max_length=50, blank=True, default="")

    # Professional Information
    experience_years = models.IntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(50)], default=0
    )
    experience_level = models.CharField(
        max_length=20, choices=EXPERIENCE_LEVEL, default="entry"
    )
    qualification = models.CharField(max_length=200, blank=True, default="")
    specialized_training = models.TextField(
        blank=True,
        default="",
        help_text="List any specialized training or certifications",
    )

    # Documents - Make these optional with defaults
    certificate = models.FileField(upload_to="certificates/", null=True, blank=True)
    identity_proof = models.FileField(
        upload_to="identity_docs/",
        null=True,
        blank=True,
        help_text="Upload government ID",
    )
    background_check = models.FileField(
        upload_to="background_checks/", null=True, blank=True
    )
    resume = models.FileField(upload_to="resumes/", null=True, blank=True)

    # Professional Details
    skills = models.TextField(
        help_text="Comma-separated list of skills", blank=True, default=""
    )
    languages = models.CharField(
        max_length=200,
        blank=True,
        default="",
        help_text="Languages spoken (comma-separated)",
    )
    employment_type = models.CharField(
        max_length=20, choices=EMPLOYMENT_TYPE, default="full_time"
    )

    # Availability
    availability_status = models.CharField(
        max_length=20, choices=AVAILABILITY_CHOICES, default="available"
    )
    available_from = models.DateField(null=True, blank=True)
    available_until = models.DateField(null=True, blank=True)
    preferred_shift = models.CharField(
        max_length=50,
        choices=[
            ("day", "Day Shift"),
            ("night", "Night Shift"),
            ("flexible", "Flexible"),
        ],
        default="flexible",
    )

    # Location
    address = models.TextField(blank=True, default="")
    city = models.CharField(max_length=100, blank=True, default="")
    state = models.CharField(max_length=100, blank=True, default="")
    country = models.CharField(max_length=100, default="India")
    pincode = models.CharField(max_length=10, blank=True, default="")
    willing_to_relocate = models.BooleanField(default=False)
    max_travel_distance = models.IntegerField(
        help_text="Maximum travel distance in kilometers", null=True, blank=True
    )

    # Professional Summary
    bio = models.TextField(max_length=500, blank=True, default="")
    achievements = models.TextField(blank=True, default="")

    # Ratings & Reviews - These will be updated via signals from the applications app
    average_rating = models.DecimalField(max_digits=3, decimal_places=2, default=0.0)
    total_reviews = models.IntegerField(default=0)
    completed_jobs = models.IntegerField(default=0)

    # Verification
    verified_by_admin = models.BooleanField(default=False)
    verification_date = models.DateTimeField(null=True, blank=True)
    verification_notes = models.TextField(blank=True, default="")

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.get_full_name()} - {self.experience_level}"

    # ==================== PROPERTIES FOR TEMPLATES ====================

    @property
    def location(self):
        """Return formatted location string (city, state, country)"""
        parts = []
        if self.city:
            parts.append(self.city)
        if self.state:
            parts.append(self.state)
        if self.country and self.country != "India":  # Only show if not default
            parts.append(self.country)

        return ", ".join(parts) if parts else None

    @property
    def full_address(self):
        """Return complete address including pincode"""
        parts = []
        if self.address:
            parts.append(self.address)
        if self.city:
            parts.append(self.city)
        if self.state:
            parts.append(self.state)
        if self.pincode:
            parts.append(self.pincode)
        if self.country:
            parts.append(self.country)

        return ", ".join(parts) if parts else None

    @property
    def display_experience(self):
        """Return formatted experience string"""
        if self.experience_years and self.experience_years > 0:
            return f"{self.experience_years} year{'' if self.experience_years == 1 else 's'}"
        return "Not specified"

    @property
    def total_assignments(self):
        """Get count of all approved assignments"""
        try:
            from . import Application

            return Application.objects.filter(caretaker=self, status="approved").count()
        except:
            return 0

    @property
    def in_progress_assignments(self):
        """Get count of in-progress assignments"""
        try:
            from . import Application

            return Application.objects.filter(
                caretaker=self, status="in_progress"
            ).count()
        except:
            return 0

    @property
    def pending_applications(self):
        """Get count of pending applications"""
        try:
            from . import Application

            return Application.objects.filter(caretaker=self, status="pending").count()
        except:
            return 0

    @property
    def display_completed_jobs(self):
        """Return completed jobs count or message"""
        if self.completed_jobs > 0:
            return self.completed_jobs
        return "0"

    @property
    def display_rating(self):
        """Return formatted rating"""
        if self.average_rating and self.average_rating > 0:
            return f"{self.average_rating} ⭐ ({self.total_reviews} review{'' if self.total_reviews == 1 else 's'})"
        return "No ratings yet"

    @property
    def availability_badge(self):
        """Return CSS class for availability status"""
        status_classes = {
            "available": "success",
            "busy": "warning",
            "fully_booked": "danger",
            "offline": "secondary",
            "on_leave": "info",
        }
        return status_classes.get(self.availability_status, "secondary")

    @property
    def is_fully_verified(self):
        """Check if caretaker is fully verified"""
        return self.verified_by_admin and self.user.is_verified

    @property
    def age(self):
        """Calculate age from date of birth"""
        if self.date_of_birth:
            today = timezone.now().date()
            return (
                today.year
                - self.date_of_birth.year
                - (
                    (today.month, today.day)
                    < (self.date_of_birth.month, self.date_of_birth.day)
                )
            )
        return None

    def update_rating(self):
        """Update average rating based on reviews"""
        # This will be called via signal when reviews are added
        try:
            from django.db.models import Avg
            from . import CaretakerReview

            avg = CaretakerReview.objects.filter(caretaker=self).aggregate(
                Avg("rating")
            )["rating__avg"]
            self.average_rating = avg or 0
            self.total_reviews = CaretakerReview.objects.filter(caretaker=self).count()
            self.save()
        except:
            # Handle case when apps.applications is not yet installed/migrated
            pass


# ---------------------------
# Family Profile (with elders field)
# ---------------------------


class FamilyProfile(models.Model):
    FAMILY_TYPE = [
        ("nuclear", "Nuclear Family"),
        ("joint", "Joint Family"),
        ("single", "Single Parent"),
        ("elderly", "Elderly Couple"),
    ]

    RESIDENCE_TYPE = [
        ("apartment", "Apartment"),
        ("independent", "Independent House"),
        ("villa", "Villa"),
        ("others", "Others"),
    ]

    GENDER_CHOICES = [
        ("male", "Male"),
        ("female", "Female"),
        ("other", "Other"),
    ]

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="family_profile"
    )

    # Elders under this family's care - ManyToMany to ElderProfile
    elders = models.ManyToManyField(
        ElderProfile,
        related_name='family_profiles',
        blank=True,
        help_text="Elderly persons under this family's care"
    )

    # Family Information
    family_type = models.CharField(
        max_length=20, choices=FAMILY_TYPE, default="nuclear"
    )
    family_size = models.IntegerField(validators=[MinValueValidator(1)], default=1)

    # Contact Information
    phone = models.CharField(max_length=15, blank=True, default="")
    alternate_phone = models.CharField(max_length=15, blank=True, default="")
    emergency_contact = models.CharField(max_length=15, blank=True, default="")

    # Address Details
    address = models.TextField(blank=True, default="")
    city = models.CharField(max_length=100, blank=True, default="")
    state = models.CharField(max_length=100, blank=True, default="")
    country = models.CharField(max_length=100, default="India")
    pincode = models.CharField(max_length=10, blank=True, default="")
    landmark = models.CharField(max_length=200, blank=True, default="")
    residence_type = models.CharField(
        max_length=20, choices=RESIDENCE_TYPE, default="apartment"
    )

    # Patient Information
    patient_name = models.CharField(max_length=100, blank=True, default="")
    patient_age = models.IntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(120)], null=True, blank=True
    )
    patient_gender = models.CharField(
        max_length=10, choices=GENDER_CHOICES, blank=True, default=""
    )
    patient_blood_group = models.CharField(
        max_length=20,
        blank=True,
        default="",
        choices=[
            ("A+", "A+"),
            ("A-", "A-"),
            ("B+", "B+"),
            ("B-", "B-"),
            ("O+", "O+"),
            ("O-", "O-"),
            ("AB+", "AB+"),
            ("AB-", "AB-"),
            ("unknown", "Unknown"),
            ("not_specified", "Not Specified"),
        ],
    )

    # Medical Information
    primary_medical_condition = models.CharField(max_length=200, blank=True, default="")
    secondary_conditions = models.TextField(blank=True, default="")
    allergies = models.TextField(blank=True, default="")
    medications = models.TextField(
        blank=True, default="", help_text="Current medications"
    )
    dietary_restrictions = models.TextField(blank=True, default="")

    # Care Requirements
    care_required = models.TextField(
        blank=True, default="", help_text="Detailed description of care needed"
    )
    care_frequency = models.CharField(
        max_length=50,
        choices=[
            ("24x7", "24/7 Care"),
            ("daily", "Daily"),
            ("weekly", "Weekly"),
            ("occasional", "Occasional"),
            ("not_specified", "Not Specified"),
        ],
        default="not_specified",
    )

    # Home Environment
    pets_at_home = models.BooleanField(default=False)
    pet_details = models.TextField(
        blank=True, default="", help_text="If yes, please specify"
    )
    smokers_in_home = models.BooleanField(default=False)
    accessibility_requirements = models.TextField(
        blank=True, default="", help_text="Any accessibility needs?"
    )

    # Previous Caretaker Experience
    previous_caretaker = models.BooleanField(default=False)
    previous_caretaker_feedback = models.TextField(blank=True, default="")

    # Documents
    identity_proof = models.FileField(
        upload_to="family_docs/", null=True, blank=True, help_text="Upload ID proof"
    )
    address_proof = models.FileField(upload_to="family_docs/", null=True, blank=True)
    medical_reports = models.FileField(
        upload_to="family_docs/",
        null=True,
        blank=True,
        help_text="Patient's medical reports",
    )

    # Verification
    verified_by_admin = models.BooleanField(default=False)
    verification_date = models.DateTimeField(null=True, blank=True)

    # Preferences
    preferred_caretaker_gender = models.CharField(
        max_length=10,
        choices=[
            ("any", "Any"),
            ("male", "Male"),
            ("female", "Female"),
        ],
        default="any",
    )

    preferred_language = models.CharField(max_length=100, blank=True, default="")

    # Budget
    monthly_budget = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.get_full_name()} - {self.patient_name or 'No patient specified'}"


# ---------------------------
# Additional Models for Enhanced Functionality
# ---------------------------


class CaretakerAvailability(models.Model):
    """Detailed availability schedule for caretakers"""

    DAYS_OF_WEEK = [
        (0, "Monday"),
        (1, "Tuesday"),
        (2, "Wednesday"),
        (3, "Thursday"),
        (4, "Friday"),
        (5, "Saturday"),
        (6, "Sunday"),
    ]

    caretaker = models.ForeignKey(
        CaretakerProfile, on_delete=models.CASCADE, related_name="availability_schedule"
    )
    day_of_week = models.IntegerField(choices=DAYS_OF_WEEK)
    start_time = models.TimeField()
    end_time = models.TimeField()
    is_available = models.BooleanField(default=True)

    class Meta:
        unique_together = ["caretaker", "day_of_week"]
        ordering = ["day_of_week", "start_time"]

    def __str__(self):
        days = dict(self.DAYS_OF_WEEK)
        return f"{self.caretaker} - {days[self.day_of_week]}: {self.start_time} to {self.end_time}"


# ---------------------------
# Application Model
# ---------------------------


class Application(models.Model):
    APPLICATION_STATUS = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("in_progress", "In Progress"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    ]

    # Relationships
    caretaker = models.ForeignKey(
        CaretakerProfile, on_delete=models.CASCADE, related_name="applications"
    )
    family = models.ForeignKey(
        FamilyProfile, on_delete=models.CASCADE, related_name="applications"
    )

    # Application details
    status = models.CharField(
        max_length=20, choices=APPLICATION_STATUS, default="pending"
    )
    applied_date = models.DateTimeField(auto_now_add=True)
    updated_date = models.DateTimeField(auto_now=True)

    # Optional fields
    notes = models.TextField(blank=True, default="")
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)

    # Payment/rate information
    agreed_rate = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )

    def __str__(self):
        return f"{self.caretaker.user.get_full_name()} - {self.family.user.get_full_name()} - {self.status}"

    class Meta:
        ordering = ["-applied_date"]


# ---------------------------
# Caretaker Review Model
# ---------------------------


class CaretakerReview(models.Model):
    RATING_CHOICES = [(i, str(i)) for i in range(1, 6)]

    caretaker = models.ForeignKey(
        CaretakerProfile, on_delete=models.CASCADE, related_name="reviews"
    )
    family = models.ForeignKey(
        FamilyProfile, on_delete=models.CASCADE, related_name="given_reviews"
    )
    application = models.OneToOneField(
        Application,
        on_delete=models.CASCADE,
        related_name="review",
        null=True,
        blank=True,
    )

    rating = models.IntegerField(choices=RATING_CHOICES)
    comment = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Review for {self.caretaker} by {self.family} - {self.rating}⭐"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Update caretaker's average rating
        self.caretaker.update_rating()