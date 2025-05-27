from django import template
from django.db.models import Sum
from calendar import month_name as calendar_month_name
from decimal import Decimal, InvalidOperation

register = template.Library()

@register.filter
def month_name(month_number):
    """Convert month number to month name."""
    try:
        return calendar_month_name[int(month_number)]
    except (IndexError, ValueError, TypeError):
        return ''

@register.filter
def spent_percentage(transactions, budget_amount):
    """Calculate the percentage of budget spent."""
    if not budget_amount:
        return 0
    
    spent = transactions.filter(type='expense').aggregate(
        total=Sum('amount')
    )['total'] or Decimal('0')
    
    return min(round((spent / Decimal(str(budget_amount))) * 100), 100)

@register.filter
def sum_amount(transactions):
    """Sum the total amount of transactions."""
    return transactions.filter(type='expense').aggregate(
        total=Sum('amount')
    )['total'] or Decimal('0')

@register.filter
def subtract(value, arg):
    """Subtract the argument from the value."""
    try:
        return Decimal(str(value)) - Decimal(str(arg))
    except (ValueError, TypeError, InvalidOperation):
        return 0

@register.filter
def monthly_amount(data, transaction_type):
    """Get monthly amounts for a specific transaction type."""
    result = {}
    for entry in data:
        if entry['type'] == transaction_type:
            result[entry['date__month']] = entry['total']
    return result

@register.filter
def get_item(dictionary, key):
    """Get an item from a dictionary."""
    return dictionary.get(key, 0) 