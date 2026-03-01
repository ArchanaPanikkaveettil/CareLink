from django import template

register = template.Library()

@register.filter
def split(value, separator=','):
    """Split a string by separator"""
    if value:
        return [item.strip() for item in value.split(separator) if item.strip()]
    return []

@register.filter
def strip(value):
    """Strip whitespace from string"""
    if value:
        return value.strip()
    return value