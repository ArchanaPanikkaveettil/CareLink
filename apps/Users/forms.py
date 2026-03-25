# apps/Users/forms.py
from django import forms
from django.contrib.auth import get_user_model

User = get_user_model()

class AdminUserEditForm(forms.ModelForm):
    """Form for admin to edit users"""
    class Meta:
        model = User
        fields = [
            'username', 'email', 'first_name', 'last_name', 
            'role', 'is_active', 'is_staff', 'is_verified', 
            'verification_status', 'phone', 'profile_picture',
            'email_notifications', 'sms_notifications'
        ]
        widgets = {
            'verification_status': forms.Select(choices=[
                ('pending', 'Pending Verification'),
                ('verified', 'Verified'),
                ('rejected', 'Rejected'),
                ('suspended', 'Suspended'),
            ]),
            'role': forms.Select(choices=[
                ('admin', 'Admin'),
                ('family', 'Family'),
                ('caretaker', 'Caretaker'),
            ]),
            'profile_picture': forms.ClearableFileInput(),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].widget.attrs.update({'class': 'form-control'})
        
        # Make profile_picture not required
        self.fields['profile_picture'].required = False


class AdminChangePasswordForm(forms.Form):
    """Admin password change form"""
    current_password = forms.CharField(widget=forms.PasswordInput)
    new_password = forms.CharField(widget=forms.PasswordInput, min_length=8)
    confirm_password = forms.CharField(widget=forms.PasswordInput)
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].widget.attrs.update({'class': 'form-control'})
    
    def clean_current_password(self):
        current = self.cleaned_data.get('current_password')
        if self.user and not self.user.check_password(current):
            raise forms.ValidationError("Current password is incorrect")
        return current
    
    def clean(self):
        cleaned_data = super().clean()
        new_password = cleaned_data.get('new_password')
        confirm_password = cleaned_data.get('confirm_password')
        
        if new_password and confirm_password and new_password != confirm_password:
            raise forms.ValidationError("New passwords do not match")
        
        # Password strength validation
        if new_password:
            if len(new_password) < 8:
                raise forms.ValidationError("Password must be at least 8 characters long")
            if not any(char.isdigit() for char in new_password):
                raise forms.ValidationError("Password must contain at least one number")
            if not any(char in "!@#$%^&*()_+-=[]{}|;:,.<>?" for char in new_password):
                raise forms.ValidationError("Password must contain at least one special character")
        
        return cleaned_data


class AdminProfilePictureForm(forms.ModelForm):
    """Profile picture upload form"""
    class Meta:
        model = User
        fields = ['profile_picture']