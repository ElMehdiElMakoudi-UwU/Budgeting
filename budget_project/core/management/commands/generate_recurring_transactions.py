from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from core.models import RecurringTransaction

class Command(BaseCommand):
    help = 'Generate transactions from recurring transactions'

    def handle(self, *args, **options):
        today = timezone.now().date()
        recurring_transactions = RecurringTransaction.objects.filter(is_active=True)
        transactions_created = 0

        for rt in recurring_transactions:
            # Skip if end date is set and passed
            if rt.end_date and rt.end_date < today:
                continue

            # Skip if start date is in the future
            if rt.start_date > today:
                continue

            last_generated = rt.last_generated or rt.start_date
            next_date = None

            # Calculate next date based on frequency
            if rt.frequency == 'daily':
                next_date = last_generated + timedelta(days=1)
            elif rt.frequency == 'weekly':
                next_date = last_generated + timedelta(weeks=1)
            elif rt.frequency == 'monthly':
                # Add one month by setting the same day in the next month
                next_date = last_generated.replace(day=1)
                if last_generated.month == 12:
                    next_date = next_date.replace(year=last_generated.year + 1, month=1)
                else:
                    next_date = next_date.replace(month=last_generated.month + 1)
                # Try to use the same day, but fall back to last day of month if necessary
                try:
                    next_date = next_date.replace(day=last_generated.day)
                except ValueError:
                    # Get last day of the month
                    if next_date.month == 12:
                        next_date = next_date.replace(year=next_date.year + 1, month=1, day=1) - timedelta(days=1)
                    else:
                        next_date = next_date.replace(month=next_date.month + 1, day=1) - timedelta(days=1)
            elif rt.frequency == 'yearly':
                next_date = last_generated.replace(year=last_generated.year + 1)

            # Generate transaction if next_date is today or in the past
            if next_date and next_date <= today:
                rt.generate_transaction()
                transactions_created += 1

        self.stdout.write(self.style.SUCCESS(f'Successfully created {transactions_created} transactions')) 