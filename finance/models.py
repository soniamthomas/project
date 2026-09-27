from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.conf import settings
from django.db import models


EXPENSE_CATEGORIES = [
	'Food',
	'Transportation',
	'Shopping',
	'Bills & Utilities',
	'Education',
	'Entertainment',
	'Health',
	'Travel',
	'Personal Care',
	'Other',
]
INCOME_CATEGORIES = ['Salary', 'Freelance', 'Scholarship', 'Allowance', 'Other']
CATEGORY_CHOICES = [(category, category) for category in dict.fromkeys(EXPENSE_CATEGORIES + INCOME_CATEGORIES)]
PAYMENT_METHOD_CHOICES = [
	('Cash', 'Cash'),
	('UPI', 'UPI'),
	('Debit Card', 'Debit Card'),
	('Credit Card', 'Credit Card'),
	('Bank Transfer', 'Bank Transfer'),
	('Other', 'Other'),
]


class Transaction(models.Model):
	class Type(models.TextChoices):
		INCOME = 'income', 'Income'
		EXPENSE = 'expense', 'Expense'

	owner = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.CASCADE,
		related_name='transactions',
		null=True,
		blank=True,
	)
	type = models.CharField(max_length=8, choices=Type.choices)
	amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
	category = models.CharField(max_length=40, choices=CATEGORY_CHOICES)
	description = models.CharField(max_length=180)
	payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES)
	transaction_date = models.DateField()
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ['-transaction_date', '-created_at']
		indexes = [models.Index(fields=['owner', 'transaction_date', 'type'])]

	def clean(self):
		super().clean()
		allowed_categories = INCOME_CATEGORIES if self.type == self.Type.INCOME else EXPENSE_CATEGORIES
		if self.category and self.category not in allowed_categories:
			raise ValidationError({'category': 'Choose a category that matches the transaction type.'})

	def __str__(self):
		return f'{self.category} - {self.amount}'


class Budget(models.Model):
	owner = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.CASCADE,
		related_name='budgets',
		null=True,
		blank=True,
	)
	category = models.CharField(max_length=40, choices=[(item, item) for item in EXPENSE_CATEGORIES])
	amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
	month = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(12)])
	year = models.PositiveSmallIntegerField(validators=[MinValueValidator(2000), MaxValueValidator(9999)])
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ['category']
		constraints = [
			models.UniqueConstraint(
				fields=['owner', 'category', 'month', 'year'],
				name='one_budget_per_owner_category_month',
			)
		]

	def __str__(self):
		return f'{self.category} budget ({self.month}/{self.year})'
from django.db import models

# Create your models here.
