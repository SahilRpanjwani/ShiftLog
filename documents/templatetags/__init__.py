from django import template

register = template.Library()

@register.filter
def get_field(obj, field_name):
    """Get an attribute or dictionary key by name."""
    if isinstance(obj, dict):
        return obj.get(field_name, '')
    return getattr(obj, field_name, '')