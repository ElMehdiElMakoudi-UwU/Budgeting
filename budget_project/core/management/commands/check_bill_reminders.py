from django.core.management.base import BaseCommand
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from core.models import BillReminder

class Command(BaseCommand):
    help = 'Check for bills that need reminders and send notifications'

    def handle(self, *args, **kwargs):
        today = timezone.now().date()
        bills = BillReminder.objects.filter(status='pending')
        
        for bill in bills:
            if bill.should_send_reminder():
                days_until_due = (bill.due_date - today).days
                
                # Prepare email message
                subject = f'Reminder: Bill "{bill.title}" due in {days_until_due} days'
                message = f"""
                This is a reminder about your upcoming bill:
                
                Title: {bill.title}
                Amount: ${bill.amount}
                Due Date: {bill.due_date}
                Category: {bill.category.name if bill.category else 'N/A'}
                
                Please ensure timely payment to avoid late fees.
                
                You can view and manage your bills at: {settings.SITE_URL}/bill-reminders/
                """
                
                try:
                    # Send email notification
                    send_mail(
                        subject,
                        message,
                        settings.DEFAULT_FROM_EMAIL,
                        [bill.user.email],
                        fail_silently=False,
                    )
                    
                    # Update last notification sent timestamp
                    bill.last_notification_sent = timezone.now()
                    bill.save()
                    
                    self.stdout.write(
                        self.style.SUCCESS(f'Successfully sent reminder for bill "{bill.title}" to {bill.user.email}')
                    )
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f'Failed to send reminder for bill "{bill.title}": {str(e)}')
                    )
        
        self.stdout.write(self.style.SUCCESS('Completed checking bill reminders')) 