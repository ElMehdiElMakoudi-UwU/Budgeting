from django.urls import path
from . import views
from rest_framework.routers import DefaultRouter
from .views import (
    ReceiptViewSet, QRPaymentViewSet, MobileNotificationViewSet,
    VoiceTransactionViewSet
)

router = DefaultRouter()
router.register(r'api/receipts', ReceiptViewSet, basename='receipt')
router.register(r'api/qr-payments', QRPaymentViewSet, basename='qr-payment')
router.register(r'api/notifications', MobileNotificationViewSet, basename='notification')
router.register(r'api/voice-transactions', VoiceTransactionViewSet, basename='voice-transaction')

urlpatterns = [
    # Dashboard
    path('', views.dashboard, name='dashboard'),
    
    # Categories
    path('categories/', views.CategoryListView.as_view(), name='category-list'),
    path('categories/add/', views.CategoryCreateView.as_view(), name='category-create'),
    path('categories/<int:pk>/edit/', views.CategoryUpdateView.as_view(), name='category-update'),
    path('categories/<int:pk>/delete/', views.CategoryDeleteView.as_view(), name='category-delete'),
    
    # Transactions
    path('transactions/', views.TransactionListView.as_view(), name='transaction-list'),
    path('transactions/add/', views.TransactionCreateView.as_view(), name='transaction-create'),
    path('transactions/<int:pk>/edit/', views.TransactionUpdateView.as_view(), name='transaction-update'),
    path('transactions/<int:pk>/delete/', views.TransactionDeleteView.as_view(), name='transaction-delete'),
    
    # Budgets
    path('budgets/', views.BudgetListView.as_view(), name='budget-list'),
    path('budgets/add/', views.BudgetCreateView.as_view(), name='budget-create'),
    path('budgets/<int:pk>/edit/', views.BudgetUpdateView.as_view(), name='budget-update'),
    path('budgets/<int:pk>/delete/', views.BudgetDeleteView.as_view(), name='budget-delete'),
    
    # Analytics
    path('analytics/', views.analytics, name='analytics'),

    # Recurring Transactions
    path('recurring-transactions/', views.RecurringTransactionListView.as_view(), name='recurring-transaction-list'),
    path('recurring-transactions/add/', views.RecurringTransactionCreateView.as_view(), name='recurring-transaction-create'),
    path('recurring-transactions/<int:pk>/edit/', views.RecurringTransactionUpdateView.as_view(), name='recurring-transaction-update'),
    path('recurring-transactions/<int:pk>/delete/', views.RecurringTransactionDeleteView.as_view(), name='recurring-transaction-delete'),
    path('recurring-transactions/<int:pk>/toggle/', views.toggle_recurring_transaction, name='recurring-transaction-toggle'),

    # Savings Goals
    path('savings-goals/', views.SavingsGoalListView.as_view(), name='savings-goal-list'),
    path('savings-goals/add/', views.SavingsGoalCreateView.as_view(), name='savings-goal-create'),
    path('savings-goals/<int:pk>/edit/', views.SavingsGoalUpdateView.as_view(), name='savings-goal-update'),
    path('savings-goals/<int:pk>/delete/', views.SavingsGoalDeleteView.as_view(), name='savings-goal-delete'),
    path('savings-goals/<int:pk>/update-amount/', views.update_savings_goal_amount, name='savings-goal-update-amount'),

    # Bill Reminders
    path('bill-reminders/', views.bill_reminders, name='bill_reminders'),
    path('bill-reminders/add/', views.add_bill_reminder, name='add_bill_reminder'),
    path('bill-reminders/<int:pk>/edit/', views.edit_bill_reminder, name='edit_bill_reminder'),
    path('bill-reminders/<int:pk>/delete/', views.delete_bill_reminder, name='delete_bill_reminder'),
    path('bill-reminders/<int:pk>/mark-paid/', views.mark_bill_as_paid, name='mark_bill_paid'),

    # Shared Expenses
    path('expense-groups/', views.expense_groups, name='expense-groups'),
    path('expense-groups/create/', views.create_expense_group, name='create-expense-group'),
    path('expense-groups/<int:pk>/', views.expense_group_detail, name='expense-group-detail'),
    path('expense-groups/<int:pk>/edit/', views.edit_expense_group, name='edit-expense-group'),
    path('expense-groups/<int:pk>/delete/', views.delete_expense_group, name='delete-expense-group'),
    path('expense-groups/<int:pk>/members/', views.manage_group_members, name='manage-group-members'),
    path('expense-groups/<int:pk>/invite/', views.invite_member, name='invite-member'),
    path('expense-groups/<int:group_pk>/expenses/create/', views.create_shared_expense, name='create-shared-expense'),
    path('expense-groups/<int:group_pk>/expenses/<int:pk>/', views.shared_expense_detail, name='shared-expense-detail'),
    path('expense-groups/<int:group_pk>/expenses/<int:pk>/edit/', views.edit_shared_expense, name='edit-shared-expense'),
    path('expense-groups/<int:group_pk>/expenses/<int:pk>/delete/', views.delete_shared_expense, name='delete-shared-expense'),
    path('expense-shares/<int:share_pk>/mark-paid/', views.mark_share_as_paid, name='mark-share-paid'),
] + router.urls 