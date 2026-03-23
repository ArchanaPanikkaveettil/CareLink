# apps/Requests/forms.py

from django import forms
from .models import CareRequest, CareBooking
from apps.Users.models import ElderProfile
from datetime import date

class CareRequestForm(forms.ModelForm):
    """Form for creating care requests"""
    
    class Meta:
        model = CareRequest
        fields = [
            'elder', 'title', 'description', 'care_type',
            'start_date', 'end_date', 'preferred_time_from', 'preferred_time_to',
            'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday',
            'hours_per_session', 'required_skills', 'special_instructions',
            'budget_per_hour', 'budget_total'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
            'required_skills': forms.Textarea(attrs={'rows': 2, 'placeholder': 'e.g., CPR, Elder Care, Medication Management'}),
            'special_instructions': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Any special instructions for the caretaker...'}),
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
            'preferred_time_from': forms.TimeInput(attrs={'type': 'time'}),
            'preferred_time_to': forms.TimeInput(attrs={'type': 'time'}),
        }
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Filter elders for this family
        if user and hasattr(user, 'family_profile'):
            self.fields['elder'].queryset = user.family_profile.elders.all()
            self.fields['elder'].required = False
    
    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        
        if start_date and start_date < date.today():
            self.add_error('start_date', 'Start date cannot be in the past')
        
        if end_date and end_date < start_date:
            self.add_error('end_date', 'End date must be after start date')
        
        return cleaned_data


class BookingForm(forms.ModelForm):
    """Form for creating a booking"""
    
    class Meta:
        model = CareBooking
        fields = ['booking_date', 'start_time', 'end_time', 'family_notes']
        widgets = {
            'booking_date': forms.DateInput(attrs={'type': 'date'}),
            'start_time': forms.TimeInput(attrs={'type': 'time'}),
            'end_time': forms.TimeInput(attrs={'type': 'time'}),
            'family_notes': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Any special instructions for this session...'}),
        }
    
    def clean(self):
        cleaned_data = super().clean()
        start_time = cleaned_data.get('start_time')
        end_time = cleaned_data.get('end_time')
        
        if start_time and end_time and end_time <= start_time:
            self.add_error('end_time', 'End time must be after start time')
        
        return cleaned_data