from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from apps.Requests.models import CareRequest

User = get_user_model()

class CareApplication(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('shortlisted', 'Shortlisted'),
        ('offer_sent', 'Offer Sent'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
        ('withdrawn', 'Withdrawn'),
        ('expired', 'Expired'),
        ('no_show', 'No Show'),
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
    
    # Shortlist fields
    shortlisted_at = models.DateTimeField(null=True, blank=True)
    shortlist_notes = models.TextField(blank=True, help_text="Private notes for family about this candidate")
    shortlist_rank = models.IntegerField(null=True, blank=True, help_text="Optional ranking of shortlisted candidates")
    
    # Offer related fields
    offer_sent_at = models.DateTimeField(null=True, blank=True)
    offer_expires_at = models.DateTimeField(null=True, blank=True)
    offer_accepted_at = models.DateTimeField(null=True, blank=True)
    offer_declined_at = models.DateTimeField(null=True, blank=True)
    offer_details = models.JSONField(null=True, blank=True, help_text="Store final offer details")
    
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
    
    class Meta:
        ordering = ['-applied_at']
        unique_together = ['caretaker', 'request']  # Prevent duplicate applications
    
    def __str__(self):
        return f"Application by {self.caretaker.username} for {self.request.patient_name}"
    
    def shortlist(self, notes="", rank=None):
        """Shortlist this application"""
        self.status = 'shortlisted'
        self.shortlisted_at = timezone.now()
        if notes:
            self.shortlist_notes = notes
        if rank:
            self.shortlist_rank = rank
        self.save()
    
    def send_offer(self, offer_details):
        """Send an offer to this caretaker"""
        self.status = 'offer_sent'
        self.offer_sent_at = timezone.now()
        self.offer_expires_at = timezone.now() + timezone.timedelta(hours=48)  # 48 hour expiry
        self.offer_details = offer_details
        self.save()
    
    def accept_offer(self):
        """Caretaker accepts the offer"""
        self.status = 'accepted'
        self.offer_accepted_at = timezone.now()
        self.save()
        
        # Update the care request
        care_request = self.request
        care_request.assigned_caretaker = self.caretaker
        care_request.assigned_date = timezone.now()
        care_request.status = 'assigned'
        care_request.save()
        
        # Reject all other applications for this request
        CareApplication.objects.filter(
            request=care_request
        ).exclude(
            id=self.id
        ).update(status='rejected')
    
    def decline_offer(self):
        """Caretaker declines the offer"""
        self.status = 'rejected'
        self.offer_declined_at = timezone.now()
        self.rejection_note = "Candidate declined the offer"
        self.save()
    
    def expire_offer(self):
        """Mark offer as expired"""
        if self.status == 'offer_sent' and self.offer_expires_at < timezone.now():
            self.status = 'expired'
            self.save()
            return True
        return False
    
    def withdraw(self):
        """Caretaker withdraws application"""
        self.status = 'withdrawn'
        self.save()
    
    def mark_care_started(self, user_role):
        """Mark that care has started"""
        if user_role == 'family':
            self.care_start_confirmed_by_family = True
        elif user_role == 'caretaker':
            self.care_start_confirmed_by_caretaker = True
        
        # If both confirmed, mark as started
        if self.care_start_confirmed_by_family and self.care_start_confirmed_by_caretaker:
            self.care_started_at = timezone.now()
            self.care_started_by = 'both'
            self.request.status = 'in_progress'
            self.request.save()
        elif self.care_start_confirmed_by_family or self.care_start_confirmed_by_caretaker:
            # One has confirmed, store who
            self.care_started_by = user_role
        
        self.save()
    
    def get_status_display_with_icon(self):
        """Return status with appropriate icon for templates"""
        icons = {
            'pending': '⏳',
            'shortlisted': '⭐',
            'offer_sent': '📧',
            'accepted': '✅',
            'rejected': '❌',
            'withdrawn': '↩️',
            'expired': '⌛',
            'no_show': '🚫',
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
                hours = remaining.seconds // 3600
                minutes = (remaining.seconds % 3600) // 60
                return f"{hours}h {minutes}m"
        return "Expired"