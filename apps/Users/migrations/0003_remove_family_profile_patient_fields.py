# Generated migration to remove redundant patient fields from FamilyProfile

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('Users', '0002_auditlog'),
    ]

    operations = [
        # Remove patient information fields
        migrations.RemoveField(
            model_name='familyprofile',
            name='patient_name',
        ),
        migrations.RemoveField(
            model_name='familyprofile',
            name='patient_age',
        ),
        migrations.RemoveField(
            model_name='familyprofile',
            name='patient_gender',
        ),
        migrations.RemoveField(
            model_name='familyprofile',
            name='patient_blood_group',
        ),
        
        # Remove medical information fields (these belong in ElderProfile)
        migrations.RemoveField(
            model_name='familyprofile',
            name='primary_medical_condition',
        ),
        migrations.RemoveField(
            model_name='familyprofile',
            name='secondary_conditions',
        ),
        migrations.RemoveField(
            model_name='familyprofile',
            name='allergies',
        ),
        migrations.RemoveField(
            model_name='familyprofile',
            name='medications',
        ),
        migrations.RemoveField(
            model_name='familyprofile',
            name='dietary_restrictions',
        ),
        
        # Remove care requirements (these are request-specific, not family-specific)
        migrations.RemoveField(
            model_name='familyprofile',
            name='care_required',
        ),
        migrations.RemoveField(
            model_name='familyprofile',
            name='care_frequency',
        ),
        
        # Update __str__ method reference (will be handled in the model update)
    ]
