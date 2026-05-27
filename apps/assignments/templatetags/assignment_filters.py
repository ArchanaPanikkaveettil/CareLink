from django import template

register = template.Library()

@register.filter
def is_read_by(note, user):
    """Check if a note is read by the given user"""
    if user.role == 'family':
        return note.read_by_family
    else:
        return note.read_by_caretaker

@register.filter
def get_item(dictionary, key):
    """Get an item from a dictionary"""
    return dictionary.get(key)