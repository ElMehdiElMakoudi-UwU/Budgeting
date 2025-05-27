from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.db.models import Sum
from django.utils import timezone
from datetime import datetime
from .models import Category, Transaction, Budget, RecurringTransaction
from django.contrib import messages
from .forms import CategoryForm, TransactionForm, BudgetForm, RecurringTransactionForm

@login_required
def dashboard(request):
    current_date = timezone.now()
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
    )

    # Recent transactions
    recent_transactions = Transaction.objects.filter(
        user=request.user
    ).order_by('-date')[:5]

    context = {
        'monthly_income': monthly_income,
        'monthly_expense': monthly_expense,
        'net_amount': monthly_income - monthly_expense,
        'budgets': budgets,
        'recent_transactions': recent_transactions,
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
        current_date = timezone.now()
        return Budget.objects.filter(
            user=self.request.user,
            month=current_date.month,
            year=current_date.year
        )

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
    # Get yearly summary
    current_year = timezone.now().year
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

    context = {
        'yearly_data': yearly_data,
        'category_summary': category_summary,
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
