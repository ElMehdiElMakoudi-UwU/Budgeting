from django import template
from django.conf import settings
from django.template.defaultfilters import floatformat

register = template.Library()

@register.filter(name='currency')
def currency(value):
    """
    Format a value as MAD currency.
    """
    try:
        value = float(value)
        formatted_value = floatformat(value, settings.CURRENCY_DECIMAL_PLACES)
        parts = str(formatted_value).split('.')
        
        # Format the integer part with thousand separators
        integer_part = parts[0]
        formatted_integer = ''
        for i, digit in enumerate(reversed(integer_part)):
            if i > 0 and i % 3 == 0:
                formatted_integer = settings.CURRENCY_THOUSAND_SEPARATOR + formatted_integer
            formatted_integer = digit + formatted_integer
            
        # Add decimal part if it exists
        if len(parts) > 1:
            formatted_value = f"{formatted_integer}{settings.CURRENCY_DECIMAL_SEPARATOR}{parts[1]}"
        else:
            formatted_value = formatted_integer
            
        return f"{formatted_value} {settings.CURRENCY_SYMBOL}"
    except (ValueError, TypeError):
        return '' 