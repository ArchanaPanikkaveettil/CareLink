from unicodedata import decimal

from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from django.db import transaction
from apps.Requests.models import CareRequest
from datetime import timedelta
import json

User = get_user_model()

class CareApplication(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('shortlisted', 'Shortlisted'),
        ('on_hold', 'On Hold'),              # When offer sent to another candidate
        ('frozen', 'Frozen'),                 # When position filled through direct accept
        ('offer_sent', 'Offer Sent'),
        ('offer_accepted', 'Offer Accepted'), # Separate from 'accepted' for clarity
        ('offer_declined', 'Offer Declined'), # Separate from 'rejected'
        ('accepted', 'Accepted'),             # Final accepted state
        ('rejected', 'Rejected'),
        ('withdrawn', 'Withdrawn'),
        ('expired', 'Expired'),
        ('no_show', 'No Show'),
        ('care_started', 'Care Started'),
        ('completed', 'Completed'),
    ]
    
    JOB_TYPE_CHOICES = [
        ('full_time', 'Full Time'),
        ('part_time', 'Part Time'),
        ('night_care', 'Night Care'),
        ('home_visit', 'Home Visit'),
        ('emergency', 'Emergency Care'),
    ]
    
    # Days of week for part-time jobs (0 = Monday, 6 = Sunday)
    DAYS_OF_WEEK = [
        (0, 'Monday'),
        (1, 'Tuesday'),
        (2, 'Wednesday'),
        (3, 'Thursday'),
        (4, 'Friday'),
        (5, 'Saturday'),
        (6, 'Sunday'),
    ]
    
    # Core fields
    request = models.ForeignKey(CareRequest, on_delete=models.CASCADE, related_name='applications')
    caretaker = models.ForeignKey(User, on_delete=models.CASCADE, related_name='applications')
    message = models.TextField()
    proposed_rate = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    applied_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    rejection_note = models.TextField(blank=True)
    
    # Job type and scheduling fields (for conflict checking)
    job_type = models.CharField(max_length=20, choices=JOB_TYPE_CHOICES, default='full_time')
    work_start_time = models.TimeField(null=True, blank=True, help_text="Start time for part-time jobs")
    work_end_time = models.TimeField(null=True, blank=True, help_text="End time for part-time jobs")
    work_days = models.JSONField(null=True, blank=True, help_text="Array of working days (0-6 where 0 is Monday)")
    
    # Shortlist fields
    shortlisted_at = models.DateTimeField(null=True, blank=True)
    shortlist_notes = models.TextField(blank=True, help_text="Private notes for family about this candidate")
    shortlist_rank = models.IntegerField(null=True, blank=True, help_text="Optional ranking of shortlisted candidates")
    
    # Hold/Frozen tracking fields
    hold_reason = models.TextField(blank=True, null=True, help_text="Reason for putting candidate on hold")
    hold_placed_at = models.DateTimeField(null=True, blank=True)
    frozen_at = models.DateTimeField(null=True, blank=True)
    frozen_reason = models.TextField(blank=True, null=True, help_text="Why this shortlist was frozen")
    
    # Offer related fields
    offer_sent_at = models.DateTimeField(null=True, blank=True)
    offer_expires_at = models.DateTimeField(null=True, blank=True)
    offer_accepted_at = models.DateTimeField(null=True, blank=True)
    offer_declined_at = models.DateTimeField(null=True, blank=True)
    offer_details = models.JSONField(null=True, blank=True, help_text="Store final offer details")
    offer_response_note = models.TextField(blank=True, help_text="Optional note from caretaker when responding to offer")
    
    # Care start tracking
    care_started_at = models.DateTimeField(null=True, blank=True)
    care_started_by = models.CharField(max_length=20, null=True, blank=True, choices=[
        ('family', 'Family'),
        ('caretaker', 'Caretaker'),
        ('both', 'Both'),
        ('auto', 'Auto'),
    ])
    care_start_confirmed_by_family = models.BooleanField(default=False)
    care_start_confirmed_by_caretaker = models.BooleanField(default=False)
    care_completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-applied_at']
        unique_together = ['caretaker', 'request']  # Prevent duplicate applications
        indexes = [
            models.Index(fields=['caretaker', 'status']),
            models.Index(fields=['request', 'status']),
            models.Index(fields=['status', 'offer_expires_at']),
        ]
    
    def __str__(self):
        return f"Application by {self.caretaker.username} for {self.request.patient_name}"
    
    # ============================================================================
    # AVAILABILITY CHECKING METHODS
    # ============================================================================
    
    def check_caretaker_availability(self):
        """
        Check if caretaker is available for this job
        Returns (is_available, reason, conflicting_assignments)
        """
        # Get all active assignments for this caretaker
        active_assignments = CareApplication.objects.filter(
            caretaker=self.caretaker,
            status__in=['accepted', 'offer_accepted', 'care_started']
        ).exclude(id=self.id).select_related('request')
        
        # If no active assignments, they're available
        if not active_assignments.exists():
            return True, "Caretaker is available", []
        
        # Check for full-time conflict
        if self.job_type == 'full_time':
            # If applying for full-time, they cannot have ANY active assignments
            return False, "You already have an active full-time assignment. Cannot apply for another full-time position.", list(active_assignments)
        
        # For part-time, check time conflicts
        if self.job_type == 'part_time' and self.work_start_time and self.work_end_time and self.work_days:
            conflicts = []
            
            for assignment in active_assignments:
                # Skip if assignment is not part-time or doesn't have schedule info
                if assignment.job_type != 'part_time' or not assignment.work_days:
                    # If they have a full-time assignment, can't do any part-time
                    if assignment.job_type == 'full_time':
                        conflicts.append(assignment)
                    continue
                
                # Check if days overlap
                current_days = set(self.work_days)
                assignment_days = set(assignment.work_days) if assignment.work_days else set()
                
                if current_days.intersection(assignment_days):
                    # Days overlap, check time overlap
                    if (self.work_start_time <= assignment.work_end_time and 
                        self.work_end_time >= assignment.work_start_time):
                        conflicts.append(assignment)
            
            if conflicts:
                return False, "This time slot conflicts with existing assignments", conflicts
            return True, "Caretaker is available for this part-time slot", []
        
        return True, "Caretaker is available", []
    
    def check_request_availability(self):
        """
        Check if the request is still available for application/offer
        Returns (is_available, reason)
        """
        if self.request.status != 'open':
            return False, f"This request is {self.request.get_status_display().lower()} and not accepting applications."
        
        if self.request.assigned_caretaker:
            return False, "This position has already been filled."
        
        return True, "Request is available"
    
    def can_apply(self, caretaker):
        """
        Check if caretaker can apply to this request
        Returns (can_apply, reason)
        """
        # Check if already applied
        if CareApplication.objects.filter(
            request=self.request,
            caretaker=caretaker
        ).exists():
            return False, "You have already applied for this request."
        
        # Create a temporary instance for availability check
        temp_app = CareApplication(
            caretaker=caretaker,
            request=self.request,
            job_type=self.request.care_type if hasattr(self.request, 'care_type') else 'full_time'
        )
        
        # Check caretaker availability
        is_available, reason, _ = temp_app.check_caretaker_availability()
        if not is_available:
            return False, reason
        
        return True, "You can apply for this position."
    
    # ============================================================================
    # STATUS CHECK METHODS
    # ============================================================================
    
    def can_be_shortlisted(self):
        """Check if application can be shortlisted"""
        if self.status != 'pending':
            return False, f"Cannot shortlist application with status: {self.get_status_display()}"
        return True, "Can be shortlisted"
    
    def can_receive_offer(self):
        """Check if can receive an offer"""
        if self.status not in ['shortlisted']:
            return False, f"Cannot send offer to application with status: {self.get_status_display()}"
        return True, "Can receive offer"
    
    def can_accept_offer(self):
        """Check if offer can be accepted"""
        if self.status != 'offer_sent':
            return False, f"Cannot accept offer with status: {self.get_status_display()}"
        
        if self.is_offer_expired():
            return False, "This offer has expired"
        
        # Check if request is still available
        available, reason = self.check_request_availability()
        if not available:
            return False, reason
        
        # Check caretaker availability
        available, reason, _ = self.check_caretaker_availability()
        if not available:
            return False, reason
        
        return True, "Can accept offer"
    
    def can_decline_offer(self):
        """Check if offer can be declined"""
        if self.status != 'offer_sent':
            return False, f"Cannot decline offer with status: {self.get_status_display()}"
        return True, "Can decline offer"
    
    def can_withdraw(self):
        """Check if application can be withdrawn"""
        if self.status not in ['pending', 'shortlisted']:
            return False, f"Cannot withdraw application with status: {self.get_status_display()}"
        return True, "Can withdraw"
    
    def can_mark_care_started(self, user_role):
        """Check if care can be marked as started"""
        if self.status not in ['accepted', 'offer_accepted']:
            return False, f"Cannot start care with status: {self.get_status_display()}"
        
        if user_role == 'family' and self.care_start_confirmed_by_family:
            return False, "You have already confirmed care started"
        
        if user_role == 'caretaker' and self.care_start_confirmed_by_caretaker:
            return False, "You have already confirmed care started"
        
        return True, "Can mark care as started"
    
    def is_active(self):
        """Check if application is active (not final state)"""
        return self.status in ['pending', 'shortlisted', 'on_hold', 'offer_sent']
    
    def is_final_state(self):
        """Check if application is in final state"""
        return self.status in ['accepted', 'offer_accepted', 'rejected', 'withdrawn', 'expired', 'completed']
    
    # ============================================================================
    # ACTION METHODS (with validation and transactions)
    # ============================================================================
    
    def shortlist(self, notes="", rank=None):
        """Shortlist this application"""
        can, reason = self.can_be_shortlisted()
        if not can:
            raise ValueError(f"Cannot shortlist: {reason}")
        
        self.status = 'shortlisted'
        self.shortlisted_at = timezone.now()
        if notes:
            self.shortlist_notes = notes
        if rank:
            self.shortlist_rank = rank
        self.save()
        return True
    
    def send_offer(self, offer_details, expiry_hours=48):
        """Send an offer to this caretaker"""
        can, reason = self.can_receive_offer()
        if not can:
            raise ValueError(f"Cannot send offer: {reason}")
        
        # Check if request is still available
        available, reason = self.check_request_availability()
        if not available:
            raise ValueError(f"Cannot send offer: {reason}")
        
        with transaction.atomic():
            self.status = 'offer_sent'
            self.offer_sent_at = timezone.now()
            self.offer_expires_at = timezone.now() + timedelta(hours=expiry_hours)
            
            # Ensure offer_details is JSON serializable
            if isinstance(offer_details, dict):
                serializable_details = {}
                for key, value in offer_details.items():
                    if isinstance(value, (str, int, float, bool, type(None))):
                        serializable_details[key] = value
                    elif isinstance(value, (decimal.Decimal,)):
                        serializable_details[key] = str(value)
                    elif hasattr(value, 'strftime'):
                        serializable_details[key] = value.isoformat() if value else None
                    else:
                        serializable_details[key] = str(value)
                self.offer_details = serializable_details
            else:
                self.offer_details = offer_details
            
            self.save()
            
            # Put other shortlisted candidates on hold
            CareApplication.objects.filter(
                request=self.request,
                status='shortlisted'
            ).exclude(
                id=self.id
            ).update(
                status='on_hold',
                hold_reason=f'Offer sent to another candidate on {timezone.now().strftime("%Y-%m-%d")}',
                hold_placed_at=timezone.now()
            )
        
        return True
    
    def accept_offer(self, note=""):
        """Caretaker accepts the offer"""
        can, reason = self.can_accept_offer()
        if not can:
            raise ValueError(f"Cannot accept offer: {reason}")
        
        with transaction.atomic():
            self.status = 'offer_accepted'
            self.offer_accepted_at = timezone.now()
            if note:
                self.offer_response_note = note
            self.save()
            
            # Update the care request
            care_request = self.request
            care_request.assigned_caretaker = self.caretaker
            care_request.assigned_date = timezone.now()
            care_request.status = 'assigned'
            care_request.save()
            
            # Freeze all other applications for this request
            CareApplication.objects.filter(
                request=care_request
            ).exclude(
                id=self.id
            ).update(
                status='rejected',
                rejection_note='Position filled by another candidate'
            )
            
            # TODO: Send notifications
            # send_offer_accepted_notification(self)
        
        return True
    
    def decline_offer(self, note=""):
        """Caretaker declines the offer"""
        can, reason = self.can_decline_offer()
        if not can:
            raise ValueError(f"Cannot decline offer: {reason}")
        
        with transaction.atomic():
            self.status = 'offer_declined'
            self.offer_declined_at = timezone.now()
            if note:
                self.offer_response_note = note
            self.save()
            
            # TODO: Send notification to family
            # send_offer_declined_notification(self)
        
        return True
    
    def expire_offer(self):
        """Mark offer as expired"""
        if self.status == 'offer_sent' and self.offer_expires_at and self.offer_expires_at < timezone.now():
            self.status = 'expired'
            self.save()
            return True
        return False
    
    def withdraw(self):
        """Caretaker withdraws application"""
        can, reason = self.can_withdraw()
        if not can:
            raise ValueError(f"Cannot withdraw: {reason}")
        
        self.status = 'withdrawn'
        self.save()
        return True
    
    def mark_care_started(self, user_role):
        """Mark that care has started"""
        can, reason = self.can_mark_care_started(user_role)
        if not can:
            raise ValueError(f"Cannot mark care started: {reason}")
        
        if user_role == 'family':
            self.care_start_confirmed_by_family = True
        elif user_role == 'caretaker':
            self.care_start_confirmed_by_caretaker = True
        
        # If both confirmed, mark as started
        if self.care_start_confirmed_by_family and self.care_start_confirmed_by_caretaker:
            with transaction.atomic():
                self.care_started_at = timezone.now()
                self.care_started_by = 'both'
                self.status = 'care_started'
                self.request.status = 'in_progress'
                self.request.save()
                self.save()
        else:
            # One has confirmed, store who
            self.care_started_by = user_role
            self.save()
        
        return True
    
    def mark_care_completed(self):
        """Mark care as completed"""
        if self.status not in ['care_started', 'in_progress']:
            raise ValueError(f"Cannot complete care with status: {self.get_status_display()}")
        
        with transaction.atomic():
            self.status = 'completed'
            self.care_completed_at = timezone.now()
            self.request.status = 'completed'
            self.request.save()
            self.save()
        
        return True
    
    def freeze_shortlist(self, reason="Position filled through direct acceptance"):
        """Freeze this shortlisted application (when direct accept happens)"""
        if self.status != 'shortlisted':
            raise ValueError(f"Cannot freeze application with status: {self.get_status_display()}")
        
        self.status = 'frozen'
        self.frozen_at = timezone.now()
        self.frozen_reason = reason
        self.save()
        return True
    
    def put_on_hold(self, reason="Offer sent to another candidate"):
        """Put this shortlisted candidate on hold"""
        if self.status != 'shortlisted':
            raise ValueError(f"Cannot put on hold application with status: {self.get_status_display()}")
        
        self.status = 'on_hold'
        self.hold_reason = reason
        self.hold_placed_at = timezone.now()
        self.save()
        return True
    
    def reactivate_from_hold(self):
        """Reactivate a candidate from on_hold back to shortlisted"""
        if self.status != 'on_hold':
            raise ValueError(f"Cannot reactivate application with status: {self.get_status_display()}")
        
        self.status = 'shortlisted'
        self.hold_reason = ''
        self.hold_placed_at = None
        self.save()
        return True
    
    # ============================================================================
    # UTILITY METHODS
    # ============================================================================
    
    def get_status_display_with_icon(self):
        """Return status with appropriate icon for templates"""
        icons = {
            'pending': '⏳',
            'shortlisted': '⭐',
            'on_hold': '⏸️',
            'frozen': '❄️',
            'offer_sent': '📧',
            'offer_accepted': '👍',
            'offer_declined': '👎',
            'accepted': '✅',
            'rejected': '❌',
            'withdrawn': '↩️',
            'expired': '⌛',
            'no_show': '🚫',
            'care_started': '🚀',
            'completed': '🏁',
        }
        return f"{icons.get(self.status, '•')} {self.get_status_display()}"
    
    def is_offer_expired(self):
        """Check if offer has expired"""
        if self.status == 'offer_sent' and self.offer_expires_at:
            return self.offer_expires_at < timezone.now()
        return False
    
    def time_until_offer_expiry(self):
        """Return time remaining for offer expiry"""
        if self.status == 'offer_sent' and self.offer_expires_at:
            remaining = self.offer_expires_at - timezone.now()
            if remaining.total_seconds() > 0:
                hours = int(remaining.total_seconds() // 3600)
                minutes = int((remaining.total_seconds() % 3600) // 60)
                return f"{hours}h {minutes}m"
        return "Expired"
    
    def get_offer_summary(self):
        """Get a human-readable summary of the offer"""
        if not self.offer_details:
            return None
        
        details = self.offer_details
        summary = []
        
        if details.get('start_date'):
            summary.append(f"Start: {details['start_date']}")
        if details.get('shift_timing'):
            summary.append(f"Shift: {details['shift_timing']}")
        if details.get('final_rate'):
            summary.append(f"Rate: ₹{details['final_rate']}/day")
        
        return " | ".join(summary)
    
    def get_work_schedule_display(self):
        """Get human-readable work schedule"""
        if self.job_type == 'full_time':
            return "Full Time"
        
        if self.job_type == 'part_time' and self.work_days and self.work_start_time and self.work_end_time:
            day_names = []
            day_map = dict(self.DAYS_OF_WEEK)
            for day in sorted(self.work_days):
                day_names.append(day_map.get(day, str(day)))
            
            days_str = ", ".join(day_names)
            time_str = f"{self.work_start_time.strftime('%H:%M')} - {self.work_end_time.strftime('%H:%M')}"
            return f"{days_str}: {time_str}"
        
        return self.get_job_type_display()
    
    # ============================================================================
    # QUERY METHODS
    # ============================================================================
    
    @classmethod
    def get_active_assignments(cls, caretaker_id):
        """Get all active assignments for a caretaker"""
        return cls.objects.filter(
            caretaker_id=caretaker_id,
            status__in=['accepted', 'offer_accepted', 'care_started']
        ).select_related('request')
    
    @classmethod
    def has_active_assignment(cls, caretaker_id):
        """Check if caretaker has any active assignment"""
        return cls.objects.filter(
            caretaker_id=caretaker_id,
            status__in=['accepted', 'offer_accepted', 'care_started']
        ).exists()
    
    @classmethod
    def get_pending_offers(cls, caretaker_id):
        """Get all pending offers for a caretaker"""
        return cls.objects.filter(
            caretaker_id=caretaker_id,
            status='offer_sent',
            offer_expires_at__gt=timezone.now()
        ).select_related('request')
    
    @classmethod
    def get_active_shortlists_for_request(cls, request_id):
        """Get all active shortlisted applications for a request"""
        return cls.objects.filter(
            request_id=request_id,
            status='shortlisted'
        ).order_by('shortlist_rank', '-shortlisted_at')
    
    @classmethod
    def has_active_shortlist(cls, request_id):
        """Check if a request has any active shortlisted candidates"""
        return cls.objects.filter(
            request_id=request_id,
            status='shortlisted'
        ).exists()
    
    @classmethod
    def cleanup_expired_offers(cls):
        """Mark all expired offers as expired"""
        expired = cls.objects.filter(
            status='offer_sent',
            offer_expires_at__lt=timezone.now()
        )
        count = expired.update(status='expired')
        return count