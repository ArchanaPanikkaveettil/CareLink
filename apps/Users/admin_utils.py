# apps/Users/admin_utils.py
import csv
import json
from io import StringIO
from datetime import datetime, timedelta
from django.http import HttpResponse
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth.models import User
from django.db.models import Count, Q, Sum
from .models import CaretakerProfile, FamilyProfile, ElderProfile


class AdminExporter:
    """Handle data export for admin panel"""
    
    @staticmethod
    def export_users_to_csv(queryset):
        """Export users to CSV"""
        output = StringIO()
        writer = csv.writer(output)
        
        # Write headers
        writer.writerow([
            'ID', 'Username', 'Email', 'First Name', 'Last Name', 
            'Role', 'Phone', 'Verified', 'Status', 'Date Joined', 'Last Login'
        ])
        
        # Write data
        for user in queryset:
            writer.writerow([
                user.id,
                user.username,
                user.email,
                user.first_name,
                user.last_name,
                user.role,
                user.phone or '',
                'Yes' if user.is_verified else 'No',
                'Active' if user.is_active else 'Inactive',
                user.date_joined.strftime('%Y-%m-%d %H:%M'),
                user.last_login.strftime('%Y-%m-%d %H:%M') if user.last_login else ''
            ])
        
        response = HttpResponse(output.getvalue(), content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename=users_{datetime.now().strftime("%Y%m%d")}.csv'
        return response
    
    @staticmethod
    def export_caretakers_to_csv(queryset):
        """Export caretakers to CSV"""
        output = StringIO()
        writer = csv.writer(output)
        
        writer.writerow([
            'ID', 'Name', 'Email', 'Phone', 'Experience (Years)', 'Qualification',
            'Skills', 'Languages', 'City', 'State', 'Availability', 'Verified'
        ])
        
        for caretaker in queryset:
            writer.writerow([
                caretaker.user.id,
                caretaker.user.get_full_name(),
                caretaker.user.email,
                caretaker.user.phone or '',
                caretaker.experience_years,
                caretaker.qualification,
                caretaker.skills,
                caretaker.languages,
                caretaker.city,
                caretaker.state,
                caretaker.availability_status,
                'Yes' if caretaker.user.is_verified else 'No'
            ])
        
        response = HttpResponse(output.getvalue(), content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename=caretakers_{datetime.now().strftime("%Y%m%d")}.csv'
        return response
    
    @staticmethod
    def export_audit_logs_to_csv(logs):
        """Export audit logs to CSV"""
        output = StringIO()
        writer = csv.writer(output)
        
        writer.writerow([
            'Timestamp', 'User', 'Action', 'Resource', 'Details', 'IP Address', 'Status'
        ])
        
        for log in logs:
            writer.writerow([
                log.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                log.user.get_full_name() if log.user else 'System',
                log.action,
                log.resource,
                log.details,
                log.ip_address or '',
                log.status
            ])
        
        response = HttpResponse(output.getvalue(), content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename=audit_logs_{datetime.now().strftime("%Y%m%d")}.csv'
        return response


class AdminStatsCalculator:
    """Calculate statistics for admin dashboard"""
    
    @staticmethod
    def get_dashboard_stats():
        """Get all dashboard statistics"""
        from django.utils import timezone
        
        today = timezone.now().date()
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)
        
        return {
            'total_users': User.objects.filter(is_active=True).count(),
            'total_caretakers': User.objects.filter(role='caretaker', is_active=True).count(),
            'total_families': User.objects.filter(role='family', is_active=True).count(),
            'pending_verifications': CaretakerProfile.objects.filter(
                user__verification_status='pending'
            ).count(),
            
            'new_users_today': User.objects.filter(date_joined__date=today).count(),
            'new_users_week': User.objects.filter(date_joined__date__gte=week_ago).count(),
            'new_users_month': User.objects.filter(date_joined__date__gte=month_ago).count(),
            
            'verified_caretakers': User.objects.filter(role='caretaker', is_verified=True).count(),
            'active_caretakers': CaretakerProfile.objects.filter(
                availability_status='available'
            ).count(),
            
            'families_with_elders': FamilyProfile.objects.filter(elders__isnull=False).distinct().count(),
            'total_elders': ElderProfile.objects.count(),
        }
    
    @staticmethod
    def get_user_growth_data(months=6):
        """Get user growth data for charts"""
        from django.utils import timezone
        from datetime import timedelta
        
        data = []
        today = timezone.now().date()
        
        for i in range(months - 1, -1, -1):
            month_start = today.replace(day=1) - timedelta(days=30 * i)
            month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
            
            new_users = User.objects.filter(
                date_joined__date__gte=month_start,
                date_joined__date__lte=month_end
            ).count()
            
            data.append({
                'month': month_start.strftime('%b %Y'),
                'new_users': new_users,
            })
        
        return data
    
    @staticmethod
    def get_user_distribution():
        """Get user role distribution"""
        return {
            'labels': ['Caretakers', 'Families'],
            'data': [
                User.objects.filter(role='caretaker', is_active=True).count(),
                User.objects.filter(role='family', is_active=True).count(),
            ]
        }


class AdminEmailService:
    """Handle email notifications for admin actions"""
    
    @staticmethod
    def send_verification_email(user, status, remarks=''):
        """Send verification status email to caretaker"""
        subject = f'Verification Update - CareLink'
        
        if status == 'approved':
            message = f"""
            Dear {user.get_full_name()},
            
            Congratulations! Your caretaker profile has been verified and approved.
            You can now start applying for care requests.
            
            {remarks if remarks else 'Welcome to CareLink!'}
            
            Best regards,
            CareLink Team
            """
        else:
            message = f"""
            Dear {user.get_full_name()},
            
            We regret to inform you that your caretaker verification was not approved.
            
            Reason: {remarks if remarks else 'Please review your submitted documents and try again.'}
            
            For any questions, please contact support.
            
            Best regards,
            CareLink Team
            """
        
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            fail_silently=True,
        )
    
    @staticmethod
    def send_admin_alert(subject, message):
        """Send alert to admin email"""
        if settings.ADMIN_EMAIL:
            send_mail(
                f'[Admin Alert] {subject}',
                message,
                settings.DEFAULT_FROM_EMAIL,
                [settings.ADMIN_EMAIL],
                fail_silently=True,
            )