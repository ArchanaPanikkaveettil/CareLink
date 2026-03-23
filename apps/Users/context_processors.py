from .models import CaretakerProfile

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