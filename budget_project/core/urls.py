from django.urls import path
from . import views

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
] 