from django.contrib import admin

from .models import Budget, Transaction


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
	list_display = ('transaction_date', 'description', 'owner', 'type', 'category', 'amount', 'payment_method')
	list_filter = ('owner', 'type', 'category', 'payment_method', 'transaction_date')
	search_fields = ('description', 'category')


@admin.register(Budget)
class BudgetAdmin(admin.ModelAdmin):
	list_display = ('category', 'owner', 'month', 'year', 'amount')
	list_filter = ('owner', 'year', 'month', 'category')
from django.contrib import admin

# Register your models here.
