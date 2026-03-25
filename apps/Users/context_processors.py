# apps/Users/context_processors.py
from .models import CaretakerProfile, FamilyProfile
from django.db.models import Q
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from apps.Notifications.models import Notification  # Fixed import

User = get_user_model()


def profile_completion_status(request):
    """Add profile completion status to context"""
    if request.user.is_authenticated and request.user.role == 'caretaker':
        try:
            profile = request.user.caretaker_profile
            # Check if profile is incomplete (missing key fields)
            incomplete = not all([
                profile.qualification,
                profile.experience_years,
                profile.city,
                profile.skills,
                profile.bio
            ])
            return {'profile_incomplete': incomplete}
        except CaretakerProfile.DoesNotExist:
            return {'profile_incomplete': True}
    return {'profile_incomplete': False}


def admin_context(request):
    """Add admin-specific context to all admin templates"""
    context = {}
    
    if request.user.is_authenticated and (request.user.is_staff or request.user.is_superuser):
        # Get counts for admin sidebar badges
        context['pending_verifications_count'] = CaretakerProfile.objects.filter(
            user__verification_status='pending'
        ).count()
        
        # Total counts
        User = get_user_model()
        context['total_users_count'] = User.objects.filter(is_active=True).count()
        context['total_caretakers_count'] = User.objects.filter(role='caretaker', is_active=True).count()
        context['total_families_count'] = User.objects.filter(role='family', is_active=True).count()
        
        # Recent activity count (last 24 hours)
        yesterday = timezone.now() - timedelta(days=1)
        
        try:
            from apps.Applications.models import Application
            context['new_applications_count'] = Application.objects.filter(
                created_at__gte=yesterday
            ).count()
        except ImportError:
            context['new_applications_count'] = 0
        
        context['is_admin'] = True
        context['is_superuser'] = request.user.is_superuser
    
    return context


def notification_count(request):
    """Add notification count to context"""
    if request.user.is_authenticated:
        try:
            unread_count = Notification.objects.filter(
                recipient=request.user,
                is_read=False
            ).count()
            return {'unread_notifications_count': unread_count}
        except:
            return {'unread_notifications_count': 0}
    return {'unread_notifications_count': 0}