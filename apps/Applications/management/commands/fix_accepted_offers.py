from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from apps.Applications.models import CareApplication
from decimal import Decimal

class Command(BaseCommand):
    help = 'Create assignments for all accepted offers and start care'

    def add_arguments(self, parser):
        parser.add_argument(
            '--application-id',
            type=int,
            help='Specific application ID to process (optional)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without actually doing it',
        )

    def handle(self, *args, **options):
        application_id = options.get('application_id')
        dry_run = options.get('dry_run', False)
        
        # Get applications to process
        if application_id:
            applications = CareApplication.objects.filter(
                id=application_id,
                status__in=['accepted', 'offer_accepted']
            )
        else:
            applications = CareApplication.objects.filter(
                status__in=['accepted', 'offer_accepted']
            )
        
        count = applications.count()
        
        if dry_run:
            self.stdout.write(f"DRY RUN: Would process {count} applications")
            for app in applications:
                self.stdout.write(f"  - ID: {app.id} | Caretaker: {app.caretaker.username} | Patient: {app.request.patient_name}")
            return
        
        processed = 0
        errors = 0
        
        for application in applications:
            try:
                self.process_application(application)
                processed += 1
                self.stdout.write(
                    self.style.SUCCESS(f"✓ Processed application #{application.id}")
                )
            except Exception as e:
                errors += 1
                self.stdout.write(
                    self.style.ERROR(f"✗ Error processing #{application.id}: {str(e)}")
                )
        
        self.stdout.write(f"\nCompleted: {processed} processed, {errors} errors")
    
    def process_application(self, application):
        with transaction.atomic():
            from apps.assignments.models import CareAssignment
            
            # Check if assignment already exists
            if CareAssignment.objects.filter(application=application).exists():
                self.stdout.write(f"  - Assignment already exists for #{application.id}")
                return
            
            care_request = application.request
            
            # Get rate details
            hourly_rate = Decimal('100')  # Default
            work_hours = 8
            
            if application.offer_details:
                final_rate = application.offer_details.get('final_rate')
                if final_rate:
                    try:
                        hourly_rate = Decimal(str(final_rate)) / 8
                    except:
                        hourly_rate = Decimal(str(final_rate))
            elif application.proposed_rate:
                hourly_rate = Decimal(str(application.proposed_rate)) / 8
            
            monthly_salary = hourly_rate * work_hours * 30
            
            # Create assignment
            assignment = CareAssignment.objects.create(
                family=care_request.family,
                caretaker=application.caretaker,
                care_request=care_request,
                application=application,
                assigned_date=application.offer_accepted_at or timezone.now(),
                start_date=care_request.start_date or timezone.now().date(),
                shift_type='full_time',
                work_hours_per_day=work_hours,
                hourly_rate=hourly_rate,
                monthly_salary=monthly_salary,
                notes=f'Created from accepted offer #{application.id}',
                status='active'
            )
            
            # Mark care as started
            application.mark_care_started('auto')
            
            self.stdout.write(f"  - Created assignment #{assignment.id} and started care")