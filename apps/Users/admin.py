# apps/Users/forms.py - Minimal version
from django import forms
from django.contrib.auth import get_user_model

User = get_user_model()

class AdminUserEditForm(forms.ModelForm):
    """Form for admin to edit users - using only fields that exist"""
    class Meta:
        model = User
        # Use only base fields that definitely exist
        fields = ['username', 'email', 'first_name', 'last_name', 'is_active', 'is_staff']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].widget.attrs.update({'class': 'form-control'})


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
        
        return cleaned_data