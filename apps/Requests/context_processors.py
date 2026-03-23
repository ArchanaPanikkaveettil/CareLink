# apps/Requests/context_processors.py
from .models import CareBooking

def booking_counts(request):
    """Add booking counts to template context"""
    context = {}
    
    if request.user.is_authenticated:
        if request.user.role == 'family':
            pending_count = CareBooking.objects.filter(
                family=request.user,
                status='pending'
            ).count()
        elif request.user.role == 'caretaker':
            pending_count = CareBooking.objects.filter(
                caretaker=request.user,
                status='pending'
            ).count()
        else:
            pending_count = 0
        
        context['pending_bookings_count'] = pending_count
    
    return context