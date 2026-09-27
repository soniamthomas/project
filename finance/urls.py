from django.urls import path

from . import views

app_name = 'finance'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('transactions/', views.transaction_list, name='transactions'),
    path('transactions/add/', views.transaction_create, name='transaction_add'),
    path('transactions/<int:pk>/edit/', views.transaction_update, name='transaction_edit'),
    path('transactions/<int:pk>/delete/', views.transaction_delete, name='transaction_delete'),
    path('transactions/export/', views.export_transactions, name='export_transactions'),
    path('analytics/', views.analytics_dashboard, name='analytics'),
    path('budgets/', views.budgets, name='budgets'),
    path('budgets/<int:pk>/edit/', views.budget_update, name='budget_edit'),
    path('budgets/<int:pk>/delete/', views.budget_delete, name='budget_delete'),
]