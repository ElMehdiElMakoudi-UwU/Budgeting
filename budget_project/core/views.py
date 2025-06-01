from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.db.models import Sum
from django.utils import timezone
from datetime import datetime
from .models import Category, Transaction, Budget, RecurringTransaction, SavingsGoal, BillReminder
from django.contrib import messages
from .forms import CategoryForm, TransactionForm, BudgetForm, RecurringTransactionForm, SavingsGoalForm, BillReminderForm
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
    ).select_related('category')[:3]  # Show top 3 active goals

    # Upcoming Bills
    upcoming_bills = BillReminder.objects.filter(
        user=request.user,
        status='pending',
        due_date__gte=current_date
    ).order_by('due_date')[:3]  # Show next 3 upcoming bills

    overdue_bills = BillReminder.objects.filter(
        user=request.user,
        status='pending',
        due_date__lt=current_date
    ).count()

    # Active Recurring Transactions
    recurring_transactions = RecurringTransaction.objects.filter(
        user=request.user,
        is_active=True
    ).select_related('category')[:3]  # Show top 3 active recurring transactions

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

    context = {
        'yearly_data': yearly_data,
        'category_summary': category_summary,
        'recurring_summary': recurring_summary,
        'savings_goals': savings_goals,
        'upcoming_bills': upcoming_bills,
        'overdue_bills': overdue_bills,
        'budget_vs_actual': budget_vs_actual,
        'current_year': current_year,
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
