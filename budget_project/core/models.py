from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from decimal import Decimal
from django.utils import timezone
from django.db.models import Sum

class Category(models.Model):
    TYPE_CHOICES = [
        ('income', 'Income'),
        ('expense', 'Expense')
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    type = models.CharField(max_length=7, choices=TYPE_CHOICES)

    def __str__(self):
        return self.name

class Transaction(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    date = models.DateField()
    note = models.TextField(blank=True)
    type = models.CharField(max_length=7, choices=Category.TYPE_CHOICES)

    def __str__(self):
        return f"{self.amount} - {self.category.name}"

class Budget(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    month = models.PositiveSmallIntegerField()
    year = models.PositiveIntegerField()

    class Meta:
        unique_together = ('user', 'category', 'month', 'year')

    def __str__(self):
        return f"{self.category.name} - {self.month}/{self.year}"

class RecurringTransaction(models.Model):
    FREQUENCY_CHOICES = [
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('yearly', 'Yearly'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    category = models.ForeignKey('Category', on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    type = models.CharField(max_length=7, choices=[('income', 'Income'), ('expense', 'Expense')])
    description = models.CharField(max_length=255)
    frequency = models.CharField(max_length=7, choices=FREQUENCY_CHOICES)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    last_generated = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_type_display()} - {self.description} ({self.get_frequency_display()})"

    def generate_transaction(self):
        """Generate a single transaction based on the recurring schedule."""
        Transaction.objects.create(
            user=self.user,
            category=self.category,
            amount=self.amount,
            type=self.type,
            date=timezone.now().date(),
            note=f"Auto-generated from recurring transaction: {self.description}"
        )
        self.last_generated = timezone.now().date()
        self.save()

class SavingsGoal(models.Model):
    STATUS_CHOICES = [
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('paused', 'Paused')
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    target_amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    current_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    target_date = models.DateField()
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=11, choices=STATUS_CHOICES, default='in_progress')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['target_date']

    def __str__(self):
        return self.name

    @property
    def progress_percentage(self):
        """Calculate the percentage of progress towards the goal."""
        if self.target_amount == 0:
            return 0
        return min(round((self.current_amount / self.target_amount) * 100), 100)

    @property
    def monthly_saving_required(self):
        """Calculate required monthly saving to reach the goal on time."""
        if self.target_date < timezone.now().date():
            return Decimal('0.00')
        
        remaining_amount = self.target_amount - self.current_amount
        months_left = (self.target_date.year - timezone.now().date().year) * 12 + \
                     (self.target_date.month - timezone.now().date().month)
        
        if months_left <= 0:
            return remaining_amount
        
        return (remaining_amount / months_left).quantize(Decimal('.01'))

class BillReminder(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('overdue', 'Overdue')
    ]

    REMINDER_CHOICES = [
        (1, '1 day before'),
        (3, '3 days before'),
        (7, '1 week before'),
        (14, '2 weeks before'),
        (30, '1 month before')
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    due_date = models.DateField()
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=7, choices=STATUS_CHOICES, default='pending')
    reminder_days = models.IntegerField(choices=REMINDER_CHOICES, default=3)
    recurring = models.BooleanField(default=False)
    recurring_frequency = models.CharField(
        max_length=7,
        choices=RecurringTransaction.FREQUENCY_CHOICES,
        null=True,
        blank=True
    )
    last_notification_sent = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['due_date']

    def __str__(self):
        return f"{self.title} - Due: {self.due_date}"

    def mark_as_paid(self):
        """Mark the bill as paid and create a corresponding transaction."""
        self.status = 'paid'
        self.save()

        # Create a transaction for the paid bill
        Transaction.objects.create(
            user=self.user,
            category=self.category,
            amount=self.amount,
            date=timezone.now().date(),
            type='expense',
            note=f"Bill payment: {self.title}"
        )

    def is_overdue(self):
        """Check if the bill is overdue."""
        return self.due_date < timezone.now().date() and self.status == 'pending'

    def should_send_reminder(self):
        """Check if a reminder should be sent based on reminder_days setting."""
        if self.status != 'pending':
            return False

        days_until_due = (self.due_date - timezone.now().date()).days
        should_remind = days_until_due <= self.reminder_days and days_until_due >= 0

        if should_remind and (
            self.last_notification_sent is None or 
            timezone.now() - self.last_notification_sent > timezone.timedelta(days=1)
        ):
            return True
        return False

    def get_next_due_date(self):
        """Calculate the next due date for recurring bills."""
        if not self.recurring:
            return None

        if self.recurring_frequency == 'daily':
            return self.due_date + timezone.timedelta(days=1)
        elif self.recurring_frequency == 'weekly':
            return self.due_date + timezone.timedelta(weeks=1)
        elif self.recurring_frequency == 'monthly':
            next_month = self.due_date.replace(day=1) + timezone.timedelta(days=32)
            return next_month.replace(day=min(self.due_date.day, (next_month.replace(day=1) - timezone.timedelta(days=1)).day))
        elif self.recurring_frequency == 'yearly':
            try:
                return self.due_date.replace(year=self.due_date.year + 1)
            except ValueError:  # Handle leap year
                return self.due_date.replace(year=self.due_date.year + 1, day=28)
        return None

class Receipt(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    image = models.ImageField(upload_to='receipts/')
    ocr_text = models.TextField(blank=True)
    processed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    merchant_name = models.CharField(max_length=255, blank=True)
    receipt_date = models.DateField(null=True, blank=True)

    def __str__(self):
        return f"Receipt {self.id} - {self.created_at.date()}"

class QRPayment(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    qr_code = models.ImageField(upload_to='qr_codes/')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.CharField(max_length=255)
    category = models.ForeignKey('Category', on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used = models.BooleanField(default=False)

    def __str__(self):
        return f"QR Payment {self.amount} - {self.description}"

class MobileNotification(models.Model):
    NOTIFICATION_TYPES = [
        ('BILL_DUE', 'Bill Due'),
        ('BUDGET_ALERT', 'Budget Alert'),
        ('GOAL_REACHED', 'Goal Reached'),
        ('RECURRING_TRANSACTION', 'Recurring Transaction'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    type = models.CharField(max_length=25, choices=NOTIFICATION_TYPES)
    title = models.CharField(max_length=255)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    read = models.BooleanField(default=False)
    sent = models.BooleanField(default=False)
    scheduled_for = models.DateTimeField(null=True, blank=True)
    related_object_id = models.IntegerField(null=True, blank=True)
    related_object_type = models.CharField(max_length=50, blank=True)

    def __str__(self):
        return f"{self.type} - {self.title}"

class VoiceTransaction(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    audio_file = models.FileField(upload_to='voice_transactions/', null=True, blank=True)
    transcription = models.TextField(blank=True)
    processed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    transaction = models.ForeignKey('Transaction', on_delete=models.SET_NULL, null=True, blank=True)
    
    def __str__(self):
        return f"Voice Transaction {self.id} - {self.created_at.date()}"

class DeviceToken(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    token = models.CharField(max_length=255, unique=True)
    device_type = models.CharField(max_length=20)  # 'ios' or 'android'
    created_at = models.DateTimeField(auto_now_add=True)
    last_used = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.user.username} - {self.device_type} Token"

class ExpenseGroup(models.Model):
    SPLIT_TYPE_CHOICES = [
        ('EQUAL', 'Split Equally'),
        ('PERCENTAGE', 'Split by Percentage'),
        ('CUSTOM', 'Custom Split'),
    ]

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_groups')
    members = models.ManyToManyField(User, through='ExpenseGroupMember', related_name='expense_groups')
    default_split_type = models.CharField(max_length=10, choices=SPLIT_TYPE_CHOICES, default='EQUAL')
    auto_approve = models.BooleanField(default=False)

    def __str__(self):
        return self.name

class ExpenseGroupMember(models.Model):
    ROLE_CHOICES = [
        ('ADMIN', 'Administrator'),
        ('MEMBER', 'Member'),
    ]

    group = models.ForeignKey(ExpenseGroup, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='MEMBER')
    joined_at = models.DateTimeField(auto_now_add=True)
    share_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=100.00)
    
    class Meta:
        unique_together = ['group', 'user']

    def __str__(self):
        return f"{self.user.username} in {self.group.name}"

class SharedExpense(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('PARTIALLY_PAID', 'Partially Paid'),
        ('PAID', 'Paid'),
        ('SETTLED', 'Settled'),
    ]

    SPLIT_TYPE_CHOICES = [
        ('EQUAL', 'Split Equally'),
        ('PERCENTAGE', 'Split by Percentage'),
        ('CUSTOM', 'Custom Split'),
    ]

    title = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField(blank=True)
    date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)
    due_date = models.DateField(null=True, blank=True)
    category = models.ForeignKey('Category', on_delete=models.SET_NULL, null=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_shared_expenses')
    group = models.ForeignKey(ExpenseGroup, on_delete=models.CASCADE)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='PENDING')
    split_type = models.CharField(max_length=10, choices=SPLIT_TYPE_CHOICES, default='EQUAL')
    receipt = models.ImageField(upload_to='shared_expense_receipts/', null=True, blank=True)

    def __str__(self):
        return f"{self.title} - {self.amount}"

    def get_member_shares(self):
        """Calculate share amount for each member based on split type."""
        if self.split_type == 'EQUAL':
            # Get active members count
            member_count = self.group.members.count()
            if member_count == 0:
                return {}
                
            # Calculate equal share amount
            share_amount = self.amount / member_count
            
            # Create shares for all members
            shares = {}
            for member in self.group.members.all():
                # The person who paid gets their share subtracted from what others owe them
                if member == self.created_by:
                    shares[member] = Decimal('0.00')
                else:
                    shares[member] = share_amount
            return shares
            
        elif self.split_type == 'PERCENTAGE':
            shares = {}
            total_percentage = Decimal('0.00')
            
            # Get all member percentages
            for member in self.group.expensegroupmember_set.all():
                if member.share_percentage > 0:
                    total_percentage += member.share_percentage
                    
            if total_percentage == 0:
                return {}
                
            # Calculate each member's share based on their percentage
            for member in self.group.expensegroupmember_set.all():
                if member.share_percentage > 0:
                    share_amount = (self.amount * member.share_percentage) / total_percentage
                    # The person who paid gets their share subtracted from what others owe them
                    if member.user == self.created_by:
                        shares[member.user] = Decimal('0.00')
                    else:
                        shares[member.user] = share_amount.quantize(Decimal('.01'))
            return shares
            
        else:  # CUSTOM
            # For custom splits, we use the ExpenseShare amounts directly
            shares = {}
            total_shares = self.shares.exclude(user=self.created_by).aggregate(
                total=Sum('amount')
            )['total'] or Decimal('0.00')
            
            # If no custom shares defined yet, return empty dict
            if total_shares == 0:
                return {}
                
            # Get all custom shares
            for share in self.shares.all():
                if share.user == self.created_by:
                    shares[share.user] = Decimal('0.00')
                else:
                    shares[share.user] = share.amount
            return shares

    def can_edit(self, user):
        """Check if the user can edit this expense."""
        # Creator can always edit
        if self.created_by == user:
            return True
        # Group admin can edit
        return self.group.expensegroupmember_set.filter(user=user, role='ADMIN').exists()

    @property
    def is_settled(self):
        """Check if the expense is fully settled."""
        return self.status == 'SETTLED'

class ExpenseShare(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('PAID', 'Paid'),
    ]

    expense = models.ForeignKey(SharedExpense, on_delete=models.CASCADE, related_name='shares')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='PENDING')
    paid_at = models.DateTimeField(null=True, blank=True)
    payment_proof = models.ImageField(upload_to='payment_proofs/', null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        unique_together = ['expense', 'user']

    def __str__(self):
        return f"{self.user.username}'s share of {self.expense.title}"

    def mark_as_paid(self):
        self.status = 'PAID'
        self.paid_at = timezone.now()
        self.save()
        
        # Check if all shares are paid and update expense status
        all_shares_paid = self.expense.shares.filter(status='PENDING').count() == 0
        if all_shares_paid:
            self.expense.status = 'SETTLED'
            self.expense.save()
