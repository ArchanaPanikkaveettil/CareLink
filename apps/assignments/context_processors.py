from .models import CareNote

def unread_messages_count(request):
    """Add unread messages count to all templates"""
    if request.user.is_authenticated:
        if request.user.role == 'family':
            count = CareNote.objects.filter(
                assignment__family=request.user,
                read_by_family=False,
                created_by__role='caretaker'  # Only count messages from caretaker
            ).count()
        elif request.user.role == 'caretaker':
            count = CareNote.objects.filter(
                assignment__caretaker=request.user,
                read_by_caretaker=False,
                created_by__role='family'  # Only count messages from family
            ).count()
        else:
            count = 0
        return {'unread_messages_count': count}
    return {'unread_messages_count': 0}