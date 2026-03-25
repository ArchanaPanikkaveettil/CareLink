# apps/Users/templatetags/users_filters.py
from django import template
from django.utils.safestring import mark_safe
import datetime

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """Get item from dictionary by key"""
    try:
        return dictionary.get(key)
    except (AttributeError, TypeError):
        return None

@register.filter
def truncate(value, length):
    """Truncate string to specified length"""
    try:
        if len(value) > length:
            return value[:length] + '...'
        return value
    except (TypeError, ValueError):
        return value

@register.filter
def has_attr(obj, attr):
    """Check if object has attribute"""
    return hasattr(obj, attr)

@register.filter
def get_attr(obj, attr):
    """Get attribute from object"""
    return getattr(obj, attr, None)

@register.filter
def format_date(value, format_string="%d %b %Y"):
    """Format date object"""
    if isinstance(value, datetime.datetime):
        return value.strftime(format_string)
    return value

@register.filter
def status_badge(status):
    """Return bootstrap badge class for status"""
    badge_map = {
        'pending': 'warning',
        'verified': 'success',
        'rejected': 'danger',
        'suspended': 'secondary',
        'active': 'success',
        'inactive': 'secondary',
        'available': 'success',
        'busy': 'warning',
        'fully_booked': 'danger',
    }
    color = badge_map.get(status.lower(), 'secondary')
    return mark_safe(f'<span class="badge bg-{color}">{status.title()}</span>')