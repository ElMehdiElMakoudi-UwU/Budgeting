from django import forms
from .models import Category, Transaction, Budget, RecurringTransaction, SavingsGoal, BillReminder

class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name', 'type']

class TransactionForm(forms.ModelForm):
    class Meta:
        model = Transaction
        fields = ['type', 'category', 'amount', 'date', 'note']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'note': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields['category'].queryset = Category.objects.filter(user=user)

class BudgetForm(forms.ModelForm):
    class Meta:
        model = Budget
        fields = ['category', 'amount', 'month', 'year']

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields['category'].queryset = Category.objects.filter(user=user, type='expense')

class RecurringTransactionForm(forms.ModelForm):
    class Meta:
        model = RecurringTransaction
        fields = ['type', 'category', 'amount', 'description', 'frequency', 'start_date', 'end_date']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields['category'].queryset = Category.objects.filter(user=user)
            
        self.fields['end_date'].required = False
        self.fields['description'].widget.attrs.update({'placeholder': 'e.g., Monthly Rent, Netflix Subscription'})

class SavingsGoalForm(forms.ModelForm):
    class Meta:
        model = SavingsGoal
        fields = ['name', 'target_amount', 'target_date', 'category', 'description']
        widgets = {
            'target_date': forms.DateInput(attrs={'type': 'date'}),
            'description': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields['category'].queryset = Category.objects.filter(user=user)
            self.fields['category'].required = False 

class BillReminderForm(forms.ModelForm):
    class Meta:
        model = BillReminder
        fields = [
            'title',
            'amount',
            'due_date',
            'category',
            'description',
            'reminder_days',
            'recurring',
            'recurring_frequency'
        ]
        widgets = {
            'due_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'description': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'reminder_days': forms.Select(attrs={'class': 'form-control'}),
            'recurring': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'recurring_frequency': forms.Select(attrs={'class': 'form-control'}),
            'category': forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields['category'].queryset = Category.objects.filter(user=user, type='expense')
        
        self.fields['recurring_frequency'].required = False
        self.fields['description'].required = False
        
        # Add help texts
        self.fields['reminder_days'].help_text = 'How many days before the due date should we remind you?'
        self.fields['recurring'].help_text = 'Check this if this is a recurring bill'
        self.fields['recurring_frequency'].help_text = 'How often does this bill repeat?'

    def clean(self):
        cleaned_data = super().clean()
        recurring = cleaned_data.get('recurring')
        recurring_frequency = cleaned_data.get('recurring_frequency')

        if recurring and not recurring_frequency:
            raise forms.ValidationError('Recurring frequency is required for recurring bills.')
        return cleaned_data 