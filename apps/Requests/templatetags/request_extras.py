# apps/Requests/templatetags/request_extras.py
from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """Get item from dictionary by key"""
    if dictionary is None:
        return None
    return dictionary.get(key)

@register.filter
def get_display_name(user):
    """Get user's display name"""
    if user:
        return user.get_full_name() or user.username
    return "Unknown"