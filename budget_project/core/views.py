from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.db.models import Sum, Q
from django.utils import timezone
from datetime import datetime
from .models import (
    Category, Transaction, Budget, RecurringTransaction, 
    SavingsGoal, BillReminder, Receipt, QRPayment, 
    MobileNotification, VoiceTransaction, ExpenseGroup,
    ExpenseGroupMember, SharedExpense, ExpenseShare
)
from django.contrib import messages
from .forms import CategoryForm, TransactionForm, BudgetForm, RecurringTransactionForm, SavingsGoalForm, BillReminderForm, ExpenseGroupForm, UserRegistrationForm
from decimal import Decimal
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .serializers import (
    ReceiptSerializer, QRPaymentSerializer, MobileNotificationSerializer,
    VoiceTransactionSerializer, DeviceTokenSerializer
)
import pytesseract
from PIL import Image
import qrcode
import speech_recognition as sr
from pydub import AudioSegment
import io
import json
import firebase_admin
from firebase_admin import credentials, messaging
from django import forms
from django.contrib.auth.models import User

@login_required
def dashboard(request):
    current_date = timezone.now().date()
    current_month = current_date.month
    current_year = current_date.year

    # Get monthly summary
    monthly_income = Transaction.objects.filter(
        user=request.user,
        type='income',
        date__month=current_month,
        date__year=current_year
    ).aggregate(Sum('amount'))['amount__sum'] or 0

    monthly_expense = Transaction.objects.filter(
        user=request.user,
        type='expense',
        date__month=current_month,
        date__year=current_year
    ).aggregate(Sum('amount'))['amount__sum'] or 0

    # Get budget progress
    budgets = Budget.objects.filter(
        user=request.user,
        month=current_month,
        year=current_year
    ).select_related('category')

    # Calculate spent amounts for each budget
    for budget in budgets:
        spent = Transaction.objects.filter(
            user=request.user,
            category=budget.category,
            type='expense',
            date__year=current_year,
            date__month=current_month
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        budget.spent_amount = spent
        budget.spent_percentage = (spent / budget.amount * 100) if budget.amount > 0 else 0
        budget.remaining = budget.amount - spent

    # Recent transactions
    recent_transactions = Transaction.objects.filter(
        user=request.user
    ).select_related('category').order_by('-date')[:5]

    # Active Savings Goals
    savings_goals = SavingsGoal.objects.filter(
        user=request.user,
        status='in_progress'
    ).select_related('category')[:3]

    # Upcoming Bills
    upcoming_bills = BillReminder.objects.filter(
        user=request.user,
        status='pending',
        due_date__gte=current_date
    ).order_by('due_date')[:3]

    overdue_bills = BillReminder.objects.filter(
        user=request.user,
        status='pending',
        due_date__lt=current_date
    ).count()

    # Active Recurring Transactions
    recurring_transactions = RecurringTransaction.objects.filter(
        user=request.user,
        is_active=True
    ).select_related('category')[:3]

    # Shared Expenses Summary
    user_groups = ExpenseGroup.objects.filter(
        members=request.user
    ).select_related('created_by')

    pending_shared_expenses = SharedExpense.objects.filter(
        group__in=user_groups,
        shares__user=request.user,
        shares__status='PENDING'
    ).count()

    recent_shared_expenses = SharedExpense.objects.filter(
        group__in=user_groups
    ).select_related('category', 'created_by').order_by('-date')[:3]

    # Calculate total owed and total to receive
    shared_expenses_owed = ExpenseShare.objects.filter(
        user=request.user,
        status='PENDING'
    ).aggregate(total=Sum('amount'))['total'] or 0

    shared_expenses_to_receive = ExpenseShare.objects.filter(
        expense__created_by=request.user,
        status='PENDING'
    ).exclude(user=request.user).aggregate(total=Sum('amount'))['total'] or 0

    context = {
        'monthly_income': monthly_income,
        'monthly_expense': monthly_expense,
        'net_amount': monthly_income - monthly_expense,
        'budgets': budgets,
        'recent_transactions': recent_transactions,
        'savings_goals': savings_goals,
        'upcoming_bills': upcoming_bills,
        'overdue_bills': overdue_bills,
        'recurring_transactions': recurring_transactions,
        'current_date': current_date,
        'pending_shared_expenses': pending_shared_expenses,
        'recent_shared_expenses': recent_shared_expenses,
        'shared_expenses_owed': shared_expenses_owed,
        'shared_expenses_to_receive': shared_expenses_to_receive,
    }
    return render(request, 'core/dashboard.html', context)

class CategoryListView(LoginRequiredMixin, ListView):
    model = Category
    template_name = 'core/category_list.html'
    context_object_name = 'categories'

    def get_queryset(self):
        return Category.objects.filter(user=self.request.user)

class CategoryCreateView(LoginRequiredMixin, CreateView):
    model = Category
    template_name = 'core/category_form.html'
    fields = ['name', 'type']
    success_url = reverse_lazy('category-list')

    def form_valid(self, form):
        form.instance.user = self.request.user
        return super().form_valid(form)

class CategoryUpdateView(LoginRequiredMixin, UpdateView):
    model = Category
    template_name = 'core/category_form.html'
    fields = ['name', 'type']
    success_url = reverse_lazy('category-list')

    def get_queryset(self):
        return Category.objects.filter(user=self.request.user)

class CategoryDeleteView(LoginRequiredMixin, DeleteView):
    model = Category
    template_name = 'core/category_confirm_delete.html'
    success_url = reverse_lazy('category-list')

    def get_queryset(self):
        return Category.objects.filter(user=self.request.user)

class TransactionListView(LoginRequiredMixin, ListView):
    model = Transaction
    template_name = 'core/transaction_list.html'
    context_object_name = 'transactions'
    ordering = ['-date']

    def get_queryset(self):
        return Transaction.objects.filter(user=self.request.user)

class TransactionCreateView(LoginRequiredMixin, CreateView):
    model = Transaction
    template_name = 'core/transaction_form.html'
    fields = ['category', 'amount', 'date', 'note', 'type']
    success_url = reverse_lazy('transaction-list')

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields['category'].queryset = Category.objects.filter(user=self.request.user)
        return form

    def form_valid(self, form):
        form.instance.user = self.request.user
        return super().form_valid(form)

class TransactionUpdateView(LoginRequiredMixin, UpdateView):
    model = Transaction
    template_name = 'core/transaction_form.html'
    fields = ['category', 'amount', 'date', 'note', 'type']
    success_url = reverse_lazy('transaction-list')

    def get_queryset(self):
        return Transaction.objects.filter(user=self.request.user)

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields['category'].queryset = Category.objects.filter(user=self.request.user)
        return form

class TransactionDeleteView(LoginRequiredMixin, DeleteView):
    model = Transaction
    template_name = 'core/transaction_confirm_delete.html'
    success_url = reverse_lazy('transaction-list')

    def get_queryset(self):
        return Transaction.objects.filter(user=self.request.user)

class BudgetListView(LoginRequiredMixin, ListView):
    model = Budget
    template_name = 'core/budget_list.html'
    context_object_name = 'budgets'

    def get_queryset(self):
        self.current_date = timezone.now().date()
        return Budget.objects.filter(
            user=self.request.user,
            month=self.current_date.month,
            year=self.current_date.year
        ).select_related('category')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['current_date'] = self.current_date
        
        # Calculate spent amounts for each budget
        for budget in context['budgets']:
            spent = Transaction.objects.filter(
                user=self.request.user,
                category=budget.category,
                type='expense',
                date__year=self.current_date.year,
                date__month=self.current_date.month
            ).aggregate(total=Sum('amount'))['total'] or 0
            
            budget.spent_amount = spent
            budget.spent_percentage = (spent / budget.amount * 100) if budget.amount > 0 else 0
            budget.remaining = budget.amount - spent
            
        return context

class BudgetCreateView(LoginRequiredMixin, CreateView):
    model = Budget
    template_name = 'core/budget_form.html'
    fields = ['category', 'amount', 'month', 'year']
    success_url = reverse_lazy('budget-list')

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields['category'].queryset = Category.objects.filter(
            user=self.request.user,
            type='expense'
        )
        current_year = timezone.now().year
        form.fields['year'].initial = current_year
        # Provide choices for 2 years before and 2 years after current year
        form.fields['year'].widget = forms.Select(choices=[
            (year, str(year)) for year in range(current_year - 2, current_year + 3)
        ])
        return form

    def form_valid(self, form):
        form.instance.user = self.request.user
        try:
            return super().form_valid(form)
        except:
            messages.error(self.request, 'Budget for this category and period already exists.')
            return self.form_invalid(form)

class BudgetUpdateView(LoginRequiredMixin, UpdateView):
    model = Budget
    template_name = 'core/budget_form.html'
    fields = ['amount']
    success_url = reverse_lazy('budget-list')

    def get_queryset(self):
        return Budget.objects.filter(user=self.request.user)

class BudgetDeleteView(LoginRequiredMixin, DeleteView):
    model = Budget
    template_name = 'core/budget_confirm_delete.html'
    success_url = reverse_lazy('budget-list')

    def get_queryset(self):
        return Budget.objects.filter(user=self.request.user)

@login_required
def analytics(request):
    current_date = timezone.now().date()
    current_year = current_date.year
    current_month = current_date.month

    # Get yearly summary
    yearly_data = Transaction.objects.filter(
        user=request.user,
        date__year=current_year
    ).values('type', 'date__month').annotate(
        total=Sum('amount')
    ).order_by('date__month')

    # Category-wise summary
    category_summary = Transaction.objects.filter(
        user=request.user,
        date__year=current_year
    ).values('category__name').annotate(
        total=Sum('amount')
    ).order_by('-total')

    # Calculate total for each category to get percentages
    total_amount = sum(cat['total'] for cat in category_summary)
    for category in category_summary:
        category['percentage'] = (category['total'] / total_amount * 100) if total_amount > 0 else 0

    # Recurring Transactions Summary
    recurring_summary = RecurringTransaction.objects.filter(
        user=request.user,
        is_active=True
    ).values('type').annotate(
        total=Sum('amount')
    )

    # Savings Goals Progress
    savings_goals = SavingsGoal.objects.filter(
        user=request.user,
        status='in_progress'
    ).select_related('category')

    # Bill Reminders Summary
    upcoming_bills = BillReminder.objects.filter(
        user=request.user,
        status='pending',
        due_date__gte=current_date
    ).order_by('due_date')[:5]

    overdue_bills = BillReminder.objects.filter(
        user=request.user,
        status='pending',
        due_date__lt=current_date
    ).count()

    # Budget vs Actual Spending
    budgets = Budget.objects.filter(
        user=request.user,
        year=current_year,
        month=current_month
    ).select_related('category')

    budget_vs_actual = []
    for budget in budgets:
        actual_spending = Transaction.objects.filter(
            user=request.user,
            category=budget.category,
            date__year=current_year,
            date__month=current_month,
            type='expense'
        ).aggregate(total=Sum('amount'))['total'] or 0

        budget_vs_actual.append({
            'category': budget.category.name,
            'budget_amount': budget.amount,
            'actual_amount': actual_spending,
            'percentage': (actual_spending / budget.amount * 100) if budget.amount > 0 else 0
        })

    # Shared Expenses Analytics
    user_groups = ExpenseGroup.objects.filter(members=request.user)
    
    # Monthly shared expenses trend
    shared_expenses_trend = SharedExpense.objects.filter(
        group__in=user_groups,
        date__year=current_year
    ).values('date__month').annotate(
        total=Sum('amount')
    ).order_by('date__month')

    # Group-wise spending
    group_spending = SharedExpense.objects.filter(
        group__in=user_groups,
        date__year=current_year
    ).values('group__name').annotate(
        total=Sum('amount')
    ).order_by('-total')

    # Personal share statistics
    personal_shares = ExpenseShare.objects.filter(
        user=request.user,
        expense__date__year=current_year
    ).aggregate(
        total_owed=Sum('amount', filter=Q(status='PENDING')),
        total_paid=Sum('amount', filter=Q(status='PAID'))
    )

    # Payment statistics (as expense creator)
    payment_stats = ExpenseShare.objects.filter(
        expense__created_by=request.user,
        expense__date__year=current_year
    ).exclude(user=request.user).aggregate(
        total_pending=Sum('amount', filter=Q(status='PENDING')),
        total_received=Sum('amount', filter=Q(status='PAID'))
    )

    context = {
        'yearly_data': yearly_data,
        'category_summary': category_summary,
        'recurring_summary': recurring_summary,
        'savings_goals': savings_goals,
        'upcoming_bills': upcoming_bills,
        'overdue_bills': overdue_bills,
        'budget_vs_actual': budget_vs_actual,
        'current_year': current_year,
        'shared_expenses_trend': shared_expenses_trend,
        'group_spending': group_spending,
        'personal_shares': personal_shares,
        'payment_stats': payment_stats,
    }
    return render(request, 'core/analytics.html', context)

class RecurringTransactionListView(LoginRequiredMixin, ListView):
    model = RecurringTransaction
    template_name = 'core/recurring_transaction_list.html'
    context_object_name = 'recurring_transactions'

    def get_queryset(self):
        return RecurringTransaction.objects.filter(user=self.request.user)

class RecurringTransactionCreateView(LoginRequiredMixin, CreateView):
    model = RecurringTransaction
    form_class = RecurringTransactionForm
    template_name = 'core/recurring_transaction_form.html'
    success_url = reverse_lazy('recurring-transaction-list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        form.instance.user = self.request.user
        messages.success(self.request, 'Recurring transaction created successfully.')
        return super().form_valid(form)

class RecurringTransactionUpdateView(LoginRequiredMixin, UpdateView):
    model = RecurringTransaction
    form_class = RecurringTransactionForm
    template_name = 'core/recurring_transaction_form.html'
    success_url = reverse_lazy('recurring-transaction-list')

    def get_queryset(self):
        return RecurringTransaction.objects.filter(user=self.request.user)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        messages.success(self.request, 'Recurring transaction updated successfully.')
        return super().form_valid(form)

class RecurringTransactionDeleteView(LoginRequiredMixin, DeleteView):
    model = RecurringTransaction
    template_name = 'core/recurring_transaction_confirm_delete.html'
    success_url = reverse_lazy('recurring-transaction-list')

    def get_queryset(self):
        return RecurringTransaction.objects.filter(user=self.request.user)

    def delete(self, request, *args, **kwargs):
        messages.success(self.request, 'Recurring transaction deleted successfully.')
        return super().delete(request, *args, **kwargs)

@login_required
def toggle_recurring_transaction(request, pk):
    recurring_transaction = get_object_or_404(RecurringTransaction, pk=pk, user=request.user)
    recurring_transaction.is_active = not recurring_transaction.is_active
    recurring_transaction.save()
    status = 'activated' if recurring_transaction.is_active else 'deactivated'
    messages.success(request, f'Recurring transaction {status} successfully.')
    return redirect('recurring-transaction-list')

class SavingsGoalListView(LoginRequiredMixin, ListView):
    model = SavingsGoal
    template_name = 'core/savings_goal_list.html'
    context_object_name = 'savings_goals'

    def get_queryset(self):
        return SavingsGoal.objects.filter(user=self.request.user)

class SavingsGoalCreateView(LoginRequiredMixin, CreateView):
    model = SavingsGoal
    form_class = SavingsGoalForm
    template_name = 'core/savings_goal_form.html'
    success_url = reverse_lazy('savings-goal-list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        form.instance.user = self.request.user
        return super().form_valid(form)

class SavingsGoalUpdateView(LoginRequiredMixin, UpdateView):
    model = SavingsGoal
    form_class = SavingsGoalForm
    template_name = 'core/savings_goal_form.html'
    success_url = reverse_lazy('savings-goal-list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get_queryset(self):
        return SavingsGoal.objects.filter(user=self.request.user)

class SavingsGoalDeleteView(LoginRequiredMixin, DeleteView):
    model = SavingsGoal
    template_name = 'core/savings_goal_confirm_delete.html'
    success_url = reverse_lazy('savings-goal-list')

    def get_queryset(self):
        return SavingsGoal.objects.filter(user=self.request.user)

@login_required
def update_savings_goal_amount(request, pk):
    goal = get_object_or_404(SavingsGoal, pk=pk, user=request.user)
    if request.method == 'POST':
        amount = request.POST.get('amount')
        try:
            amount = Decimal(amount)
            goal.current_amount = amount
            if amount >= goal.target_amount:
                goal.status = 'completed'
            elif goal.status == 'completed':
                goal.status = 'in_progress'
            goal.save()
            messages.success(request, 'Savings goal amount updated successfully!')
        except:
            messages.error(request, 'Invalid amount provided.')
    return redirect('savings-goal-list')

@login_required
def bill_reminders(request):
    """View for listing and managing bill reminders."""
    bills = BillReminder.objects.filter(user=request.user).order_by('due_date')
    
    # Update overdue status
    for bill in bills:
        if bill.is_overdue():
            bill.status = 'overdue'
            bill.save()

    context = {
        'bills': bills,
        'pending_bills': bills.filter(status='pending').count(),
        'overdue_bills': bills.filter(status='overdue').count(),
    }
    return render(request, 'core/bill_reminders.html', context)

@login_required
def add_bill_reminder(request):
    """View for adding a new bill reminder."""
    if request.method == 'POST':
        form = BillReminderForm(request.POST, user=request.user)
        if form.is_valid():
            bill = form.save(commit=False)
            bill.user = request.user
            bill.save()
            messages.success(request, 'Bill reminder added successfully!')
            return redirect('bill_reminders')
    else:
        form = BillReminderForm(user=request.user)
    
    return render(request, 'core/bill_reminder_form.html', {'form': form, 'title': 'Add Bill Reminder'})

@login_required
def edit_bill_reminder(request, pk):
    """View for editing an existing bill reminder."""
    bill = get_object_or_404(BillReminder, pk=pk, user=request.user)
    
    if request.method == 'POST':
        form = BillReminderForm(request.POST, instance=bill, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Bill reminder updated successfully!')
            return redirect('bill_reminders')
    else:
        form = BillReminderForm(instance=bill, user=request.user)
    
    return render(request, 'core/bill_reminder_form.html', {'form': form, 'title': 'Edit Bill Reminder'})

@login_required
def delete_bill_reminder(request, pk):
    """View for deleting a bill reminder."""
    bill = get_object_or_404(BillReminder, pk=pk, user=request.user)
    
    if request.method == 'POST':
        bill.delete()
        messages.success(request, 'Bill reminder deleted successfully!')
        return redirect('bill_reminders')
    
    return render(request, 'core/confirm_delete.html', {'object': bill, 'object_type': 'bill reminder'})

@login_required
def mark_bill_as_paid(request, pk):
    """View for marking a bill as paid."""
    bill = get_object_or_404(BillReminder, pk=pk, user=request.user)
    
    if request.method == 'POST':
        bill.mark_as_paid()
        messages.success(request, f'Bill "{bill.title}" marked as paid!')
        
        # Handle recurring bills
        if bill.recurring:
            next_due_date = bill.get_next_due_date()
            if next_due_date:
                # Create next bill reminder
                BillReminder.objects.create(
                    user=request.user,
                    title=bill.title,
                    amount=bill.amount,
                    due_date=next_due_date,
                    category=bill.category,
                    description=bill.description,
                    reminder_days=bill.reminder_days,
                    recurring=True,
                    recurring_frequency=bill.recurring_frequency
                )
                messages.info(request, f'Next bill reminder created for {next_due_date}')
    
    return redirect('bill_reminders')

class ReceiptViewSet(viewsets.ModelViewSet):
    serializer_class = ReceiptSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Receipt.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        receipt = serializer.save(user=self.request.user)
        # Process the receipt image with OCR
        try:
            image = Image.open(receipt.image)
            ocr_text = pytesseract.image_to_string(image)
            receipt.ocr_text = ocr_text
            
            # Extract information from OCR text
            lines = ocr_text.split('\n')
            for line in lines:
                if '$' in line:
                    # Try to extract amount
                    amount = line.split('$')[1].strip().split()[0]
                    try:
                        receipt.total_amount = float(amount.replace(',', ''))
                    except ValueError:
                        pass
                
            receipt.processed = True
            receipt.save()
        except Exception as e:
            receipt.ocr_text = f"Error processing receipt: {str(e)}"
            receipt.save()

class QRPaymentViewSet(viewsets.ModelViewSet):
    serializer_class = QRPaymentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return QRPayment.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        payment = serializer.save(user=self.request.user)
        
        # Generate QR code
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        data = {
            'amount': str(payment.amount),
            'description': payment.description,
            'expires_at': payment.expires_at.isoformat(),
            'id': payment.id
        }
        qr.add_data(json.dumps(data))
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        
        # Save the QR code
        from django.core.files.base import ContentFile
        payment.qr_code.save(f'qr_payment_{payment.id}.png', ContentFile(buffer.getvalue()), save=True)

class MobileNotificationViewSet(viewsets.ModelViewSet):
    serializer_class = MobileNotificationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return MobileNotification.objects.filter(user=self.request.user)

    @action(detail=False, methods=['post'])
    def register_device(self, request):
        serializer = DeviceTokenSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(user=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def send_push_notification(self, token, title, body):
        try:
            message = messaging.Message(
                notification=messaging.Notification(
                    title=title,
                    body=body,
                ),
                token=token,
            )
            response = messaging.send(message)
            return True
        except Exception as e:
            print(f"Error sending notification: {e}")
            return False

class VoiceTransactionViewSet(viewsets.ModelViewSet):
    serializer_class = VoiceTransactionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return VoiceTransaction.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        voice_transaction = serializer.save(user=self.request.user)
        
        try:
            # Convert audio file to wav format
            audio = AudioSegment.from_file(voice_transaction.audio_file)
            wav_file = io.BytesIO()
            audio.export(wav_file, format="wav")
            
            # Perform speech recognition
            recognizer = sr.Recognizer()
            with sr.AudioFile(wav_file) as source:
                audio_data = recognizer.record(source)
                text = recognizer.recognize_google(audio_data)
                
            voice_transaction.transcription = text
            
            # Try to parse transaction details from transcription
            # Example: "Spent 50 dollars on groceries"
            words = text.lower().split()
            amount = None
            category = None
            
            for i, word in enumerate(words):
                if word.isdigit():
                    amount = float(word)
                    break
                    
            # Look for category keywords
            categories = Category.objects.filter(user=self.request.user)
            for category in categories:
                if category.name.lower() in text.lower():
                    category = category
                    break
            
            if amount and category:
                transaction = Transaction.objects.create(
                    user=self.request.user,
                    amount=amount,
                    category=category,
                    description=text
                )
                voice_transaction.transaction = transaction
                
            voice_transaction.processed = True
            voice_transaction.save()
            
        except Exception as e:
            voice_transaction.transcription = f"Error processing voice: {str(e)}"
            voice_transaction.save()

@login_required
def expense_groups(request):
    """View for listing user's expense groups."""
    expense_groups = ExpenseGroup.objects.filter(
        Q(members=request.user) | Q(created_by=request.user)
    ).distinct()
    
    # Calculate additional stats for each group
    for group in expense_groups:
        group.member_count = group.members.count()
        group.expense_count = SharedExpense.objects.filter(group=group).count()
        
        # Calculate user balance
        user_shares = ExpenseShare.objects.filter(
            expense__group=group,
            user=request.user
        ).aggregate(
            total_owed=Sum('amount', filter=Q(status='PENDING')),
            total_paid=Sum('amount', filter=Q(status='PAID'))
        )
        
        group.user_balance = (user_shares['total_paid'] or 0) - (user_shares['total_owed'] or 0)
    
    # Calculate totals for summary cards
    total_paid = ExpenseShare.objects.filter(
        user=request.user,
        status='PAID'
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    total_pending = ExpenseShare.objects.filter(
        user=request.user,
        status='PENDING'
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    total_to_receive = ExpenseShare.objects.filter(
        expense__created_by=request.user,
        status='PENDING'
    ).exclude(user=request.user).aggregate(total=Sum('amount'))['total'] or 0
    
    context = {
        'expense_groups': expense_groups,
        'total_paid': total_paid,
        'total_pending': total_pending,
        'total_to_receive': total_to_receive,
        'pending_expenses': SharedExpense.objects.filter(
            group__in=expense_groups,
            shares__user=request.user,
            shares__status='PENDING'
        ).count()
    }
    return render(request, 'core/expense_groups.html', context)

@login_required
def create_expense_group(request):
    """View for creating a new expense group."""
    if request.method == 'POST':
        form = ExpenseGroupForm(request.POST)
        if form.is_valid():
            group = form.save(commit=False)
            group.created_by = request.user
            group.save()
            
            # Add creator as admin
            ExpenseGroupMember.objects.create(
                group=group,
                user=request.user,
                role='ADMIN'
            )
            
            # Add other members
            for email in form.cleaned_data['members']:
                try:
                    user = User.objects.get(email=email)
                    if user != request.user:
                        ExpenseGroupMember.objects.create(
                            group=group,
                            user=user
                        )
                except User.DoesNotExist:
                    messages.warning(request, f'User with email {email} not found')
            
            messages.success(request, 'Expense group created successfully!')
            return redirect('expense-group-detail', pk=group.pk)
    else:
        form = ExpenseGroupForm()
    
    return render(request, 'core/expense_group_form.html', {'form': form})

@login_required
def expense_group_detail(request, pk):
    """View for showing expense group details and expenses."""
    group = get_object_or_404(ExpenseGroup, pk=pk)
    if not group.members.filter(id=request.user.id).exists():
        messages.error(request, 'You do not have access to this group')
        return redirect('expense-groups')
    
    expenses = SharedExpense.objects.filter(group=group).order_by('-date')
    member_shares = {}
    
    # Calculate total expenses in the group
    total_expenses = expenses.aggregate(total=Sum('amount'))['total'] or 0
    
    # Calculate user's total share
    user_shares = ExpenseShare.objects.filter(
        expense__group=group,
        user=request.user
    ).aggregate(
        total=Sum('amount'),
        total_paid=Sum('amount', filter=Q(status='PAID')),
        total_pending=Sum('amount', filter=Q(status='PENDING'))
    )
    
    user_share = user_shares['total'] or 0
    you_owe = user_shares['total_pending'] or 0
    
    # Calculate amount others owe to the user
    youre_owed = ExpenseShare.objects.filter(
        expense__group=group,
        expense__created_by=request.user,
        status='PENDING'
    ).exclude(user=request.user).aggregate(total=Sum('amount'))['total'] or 0
    
    # Get all members with their roles and balances
    members = []
    for member in group.expensegroupmember_set.select_related('user').all():
        # Calculate member's balance
        member_shares = ExpenseShare.objects.filter(
            expense__group=group,
            user=member.user
        ).aggregate(
            total_owed=Sum('amount', filter=Q(status='PENDING')),
            total_paid=Sum('amount', filter=Q(status='PAID'))
        )
        
        # Calculate amount this member owes to others
        owed_to_others = member_shares['total_owed'] or 0
        
        # Calculate amount others owe to this member
        owed_by_others = ExpenseShare.objects.filter(
            expense__group=group,
            expense__created_by=member.user,
            status='PENDING'
        ).exclude(user=member.user).aggregate(total=Sum('amount'))['total'] or 0
        
        # Calculate net balance
        balance = (member_shares['total_paid'] or 0) - owed_to_others + owed_by_others
        
        members.append({
            'user': member.user,
            'is_admin': member.role == 'ADMIN',
            'balance': balance
        })
    
    context = {
        'group': group,
        'expenses': expenses,
        'members': members,
        'is_admin': group.expensegroupmember_set.filter(user=request.user, role='ADMIN').exists(),
        'total_expenses': total_expenses,
        'user_share': user_share,
        'you_owe': you_owe,
        'youre_owed': youre_owed
    }
    return render(request, 'core/expense_group_detail.html', context)

@login_required
def create_shared_expense(request, group_pk):
    """View for creating a new shared expense."""
    group = get_object_or_404(ExpenseGroup, pk=group_pk)
    if not group.members.filter(id=request.user.id).exists():
        messages.error(request, 'You do not have access to this group')
        return redirect('expense-groups')
    
    if request.method == 'POST':
        title = request.POST.get('title')
        amount = Decimal(request.POST.get('amount', '0'))
        description = request.POST.get('description')
        date = request.POST.get('date')
        category_id = request.POST.get('category')
        split_type = request.POST.get('split_type')
        due_date = request.POST.get('due_date')
        
        # Create the expense
        expense = SharedExpense.objects.create(
            title=title,
            amount=amount,
            description=description,
            date=date,
            category_id=category_id,
            created_by=request.user,
            group=group,
            split_type=split_type,
            due_date=due_date if due_date else None
        )
        
        # Handle different split types
        if split_type == 'EQUAL':
            # Equal split - divide amount among all members
            member_count = group.members.count()
            if member_count > 0:
                share_amount = amount / member_count
                for member in group.members.all():
                    if member != request.user:  # Skip the creator
                        ExpenseShare.objects.create(
                            expense=expense,
                            user=member,
                            amount=share_amount
                        )
                    
        elif split_type == 'PERCENTAGE':
            # Get user-defined percentages from form
            total_percentage = Decimal('0')
            shares = {}
            
            # First, collect all percentages and validate total
            for member in group.members.exclude(id=request.user.id):
                percentage = Decimal(request.POST.get(f'percentage_{member.id}', '0'))
                if percentage > 0:
                    total_percentage += percentage
                    shares[member] = percentage
            
            # Validate total percentage
            if total_percentage > 100:
                expense.delete()
                messages.error(request, 'Total percentage cannot exceed 100%')
                return redirect('create-shared-expense', group_pk=group_pk)
            elif total_percentage == 0:
                expense.delete()
                messages.error(request, 'Please set percentage shares for members')
                return redirect('create-shared-expense', group_pk=group_pk)
            
            # Create shares based on percentages
            for member, percentage in shares.items():
                share_amount = (amount * percentage / 100).quantize(Decimal('.01'))
                ExpenseShare.objects.create(
                    expense=expense,
                    user=member,
                    amount=share_amount
                )
                    
        else:  # CUSTOM
            # Custom split - get amounts from form
            for member in group.members.exclude(id=request.user.id):
                share_amount = request.POST.get(f'share_amount_{member.id}', None)
                if share_amount:
                    ExpenseShare.objects.create(
                        expense=expense,
                        user=member,
                        amount=Decimal(share_amount)
                    )
        
        messages.success(request, 'Shared expense created successfully!')
        return redirect('expense-group-detail', pk=group_pk)
    
    # Get all members except the current user for the percentage split
    members = group.members.exclude(id=request.user.id).select_related('user')
    
    categories = Category.objects.filter(
        Q(user=request.user) | Q(user__in=group.members.all()),
        type='expense'
    ).distinct()
    
    context = {
        'group': group,
        'categories': categories,
        'members': members,
        'expense': None  # Add this to handle the template's expense checks
    }
    return render(request, 'core/shared_expense_form.html', context)

@login_required
def mark_share_as_paid(request, share_pk):
    """View for marking an expense share as paid."""
    share = get_object_or_404(ExpenseShare, pk=share_pk, user=request.user)
    
    if request.method == 'POST':
        payment_proof = request.FILES.get('payment_proof')
        notes = request.POST.get('notes')
        
        share.payment_proof = payment_proof
        share.notes = notes
        share.mark_as_paid()
        
        messages.success(request, 'Payment marked as completed!')
        return redirect('expense-group-detail', pk=share.expense.group.pk)
    
    return render(request, 'core/mark_share_paid.html', {'share': share})

@login_required
def edit_expense_group(request, pk):
    """View for editing an expense group."""
    group = get_object_or_404(ExpenseGroup, pk=pk)
    if not group.expensegroupmember_set.filter(user=request.user, role='ADMIN').exists():
        messages.error(request, 'You do not have permission to edit this group')
        return redirect('expense-group-detail', pk=pk)
    
    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description')
        
        group.name = name
        group.description = description
        group.save()
        
        messages.success(request, 'Group updated successfully!')
        return redirect('expense-group-detail', pk=pk)
    
    return render(request, 'core/expense_group_form.html', {'group': group})

@login_required
def delete_expense_group(request, pk):
    """View for deleting an expense group."""
    group = get_object_or_404(ExpenseGroup, pk=pk)
    if not group.expensegroupmember_set.filter(user=request.user, role='ADMIN').exists():
        messages.error(request, 'You do not have permission to delete this group')
        return redirect('expense-group-detail', pk=pk)
    
    if request.method == 'POST':
        group.delete()
        messages.success(request, 'Group deleted successfully!')
        return redirect('expense-groups')
    
    return render(request, 'core/expense_group_confirm_delete.html', {'group': group})

@login_required
def manage_group_members(request, pk):
    """View for managing group members."""
    group = get_object_or_404(ExpenseGroup, pk=pk)
    if not group.expensegroupmember_set.filter(user=request.user, role='ADMIN').exists():
        messages.error(request, 'You do not have permission to manage members')
        return redirect('expense-group-detail', pk=pk)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        member_id = request.POST.get('member_id')
        
        if action == 'remove':
            member = get_object_or_404(ExpenseGroupMember, pk=member_id)
            if member.user != request.user:  # Prevent self-removal
                member.delete()
                messages.success(request, 'Member removed successfully!')
        elif action == 'make_admin':
            member = get_object_or_404(ExpenseGroupMember, pk=member_id)
            member.role = 'ADMIN'
            member.save()
            messages.success(request, 'Member promoted to admin!')
    
    members = group.expensegroupmember_set.select_related('user').all()
    return render(request, 'core/expense_group_members.html', {'group': group, 'members': members})

@login_required
def invite_member(request, pk):
    """View for inviting new members to the group."""
    group = get_object_or_404(ExpenseGroup, pk=pk)
    if not group.expensegroupmember_set.filter(user=request.user, role='ADMIN').exists():
        messages.error(request, 'You do not have permission to invite members')
        return redirect('expense-group-detail', pk=pk)
    
    if request.method == 'POST':
        email = request.POST.get('email')
        try:
            user = User.objects.get(email=email)
            if not group.members.filter(id=user.id).exists():
                ExpenseGroupMember.objects.create(group=group, user=user)
                messages.success(request, f'{user.get_full_name() or user.username} added to the group!')
            else:
                messages.warning(request, 'User is already a member of this group')
        except User.DoesNotExist:
            messages.error(request, f'No user found with email {email}')
    
    return redirect('manage-group-members', pk=pk)

@login_required
def shared_expense_detail(request, group_pk, pk):
    """View for showing shared expense details."""
    expense = get_object_or_404(SharedExpense, pk=pk, group_id=group_pk)
    if not expense.group.members.filter(id=request.user.id).exists():
        messages.error(request, 'You do not have access to this expense')
        return redirect('expense-groups')
    
    return render(request, 'core/shared_expense_detail.html', {'expense': expense})

@login_required
def edit_shared_expense(request, group_pk, pk):
    """View for editing a shared expense."""
    expense = get_object_or_404(SharedExpense, pk=pk, group_id=group_pk)
    if not expense.can_edit(request.user):
        messages.error(request, 'You do not have permission to edit this expense')
        return redirect('shared-expense-detail', group_pk=group_pk, pk=pk)
    
    if request.method == 'POST':
        title = request.POST.get('title')
        amount = request.POST.get('amount')
        description = request.POST.get('description')
        date = request.POST.get('date')
        category_id = request.POST.get('category')
        split_type = request.POST.get('split_type')
        due_date = request.POST.get('due_date')
        
        expense.title = title
        expense.amount = Decimal(amount)
        expense.description = description
        expense.date = date
        expense.category_id = category_id
        expense.split_type = split_type
        expense.due_date = due_date if due_date else None
        expense.save()
        
        # Update shares based on new split type and amount
        shares = expense.get_member_shares()
        for user, amount in shares.items():
            ExpenseShare.objects.update_or_create(
                expense=expense,
                user=user,
                defaults={'amount': amount}
            )
        
        messages.success(request, 'Expense updated successfully!')
        return redirect('shared-expense-detail', group_pk=group_pk, pk=pk)
    
    categories = Category.objects.filter(
        Q(user=request.user) | Q(user__in=expense.group.members.all()),
        type='expense'
    ).distinct()
    
    return render(request, 'core/shared_expense_form.html', {
        'expense': expense,
        'categories': categories
    })

@login_required
def delete_shared_expense(request, group_pk, pk):
    """View for deleting a shared expense."""
    expense = get_object_or_404(SharedExpense, pk=pk, group_id=group_pk)
    if not expense.can_edit(request.user):
        messages.error(request, 'You do not have permission to delete this expense')
        return redirect('shared-expense-detail', group_pk=group_pk, pk=pk)
    
    if request.method == 'POST':
        expense.delete()
        messages.success(request, 'Expense deleted successfully!')
        return redirect('expense-group-detail', pk=group_pk)
    
    return render(request, 'core/shared_expense_confirm_delete.html', {'expense': expense})

def register(request):
    """View for user registration."""
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(request, 'Account created successfully! You can now login.')
            return redirect('login')
    else:
        form = UserRegistrationForm()
    return render(request, 'registration/register.html', {'form': form})
