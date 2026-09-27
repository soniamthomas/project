from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from .analytics import analyze_transactions, get_date_bounds
from .models import Budget, Transaction


class AuthenticatedFinanceTestCase(TestCase):
	def setUp(self):
		self.user = get_user_model().objects.create_user(username='ledger-user', password='Ledger-test-pass-52!')
		self.client.force_login(self.user)


class AuthenticationViewTests(TestCase):
	def test_login_and_registration_pages_render(self):
		self.assertContains(self.client.get(reverse('login')), 'Sign in to Ledgerly')
		self.assertContains(self.client.get(reverse('register')), 'Create your account')

	def test_registration_creates_account_and_signs_user_in(self):
		response = self.client.post(reverse('register'), {
			'username': 'new-ledger-user',
			'password1': 'Ledger-registration-pass-38!',
			'password2': 'Ledger-registration-pass-38!',
		})

		self.assertRedirects(response, reverse('finance:dashboard'))
		self.assertTrue(get_user_model().objects.filter(username='new-ledger-user').exists())
		self.assertIn('_auth_user_id', self.client.session)

	def test_login_and_logout(self):
		get_user_model().objects.create_user(username='returning-user', password='Ledger-login-pass-52!')
		response = self.client.post(reverse('login'), {
			'username': 'returning-user',
			'password': 'Ledger-login-pass-52!',
		})
		self.assertRedirects(response, reverse('finance:dashboard'))

		response = self.client.post(reverse('logout'))
		self.assertRedirects(response, reverse('login'))
		self.assertNotIn('_auth_user_id', self.client.session)

	def test_finance_pages_require_authentication(self):
		for url in (
			reverse('finance:dashboard'),
			reverse('finance:transactions'),
			reverse('finance:transaction_add'),
			reverse('finance:export_transactions'),
			reverse('finance:analytics'),
			reverse('finance:budgets'),
		):
			with self.subTest(url=url):
				response = self.client.get(url, HTTP_HOST='127.0.0.1')
				self.assertEqual(response.status_code, 302)
				self.assertTrue(response.url.startswith(reverse('login')))


class ProfileViewTests(AuthenticatedFinanceTestCase):
	def test_profile_page_shows_current_details(self):
		self.user.first_name = 'Ledger'
		self.user.email = 'ledger@example.com'
		self.user.save()

		response = self.client.get(reverse('profile'))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'Personal profile')
		self.assertEqual(response.context['form'].instance, self.user)

	def test_profile_updates_only_the_signed_in_user(self):
		other_user = get_user_model().objects.create_user(
			username='another-user', password='Other-pass-42!', email='other@example.com',
		)
		response = self.client.post(reverse('profile'), {
			'username': 'ledger-updated',
			'email': 'updated@example.com',
			'first_name': 'Ledger',
			'last_name': 'Member',
		})

		self.assertRedirects(response, reverse('profile'))
		self.user.refresh_from_db()
		other_user.refresh_from_db()
		self.assertEqual(self.user.username, 'ledger-updated')
		self.assertEqual(self.user.email, 'updated@example.com')
		self.assertEqual(self.user.first_name, 'Ledger')
		self.assertEqual(self.user.last_name, 'Member')
		self.assertEqual(other_user.username, 'another-user')

	def test_profile_rejects_a_username_used_by_another_account(self):
		get_user_model().objects.create_user(username='taken-name', password='Other-pass-42!')
		response = self.client.post(reverse('profile'), {
			'username': 'taken-name',
			'email': '',
			'first_name': '',
			'last_name': '',
		})

		self.assertEqual(response.status_code, 200)
		self.assertIn('username', response.context['form'].errors)
		self.user.refresh_from_db()
		self.assertEqual(self.user.username, 'ledger-user')


class AccountIsolationTests(AuthenticatedFinanceTestCase):
	def test_finance_records_are_limited_to_the_signed_in_user(self):
		other_user = get_user_model().objects.create_user(username='another-user', password='Other-pass-42!')
		Transaction.objects.create(
			owner=self.user, type='expense', amount=Decimal('25'), category='Food',
			description='My lunch', payment_method='Cash', transaction_date=date(2026, 9, 10),
		)
		Transaction.objects.create(
			owner=other_user, type='expense', amount=Decimal('90'), category='Shopping',
			description='Someone else purchase', payment_method='Cash', transaction_date=date(2026, 9, 10),
		)
		own_budget = Budget.objects.create(
			owner=self.user, category='Food', amount=Decimal('500'), month=9, year=2026,
		)
		Budget.objects.create(
			owner=other_user, category='Shopping', amount=Decimal('900'), month=9, year=2026,
		)

		response = self.client.get(reverse('finance:transactions'))
		self.assertContains(response, 'My lunch')
		self.assertNotContains(response, 'Someone else purchase')

		response = self.client.get(reverse('finance:budgets'), {'month': 9, 'year': 2026})
		self.assertEqual([row['budget'].pk for row in response.context['budget_rows']], [own_budget.pk])

	def test_user_cannot_edit_or_delete_another_users_records(self):
		other_user = get_user_model().objects.create_user(username='another-user', password='Other-pass-42!')
		other_transaction = Transaction.objects.create(
			owner=other_user, type='expense', amount=Decimal('25'), category='Food',
			description='Private lunch', payment_method='Cash', transaction_date=date(2026, 9, 10),
		)
		other_budget = Budget.objects.create(
			owner=other_user, category='Food', amount=Decimal('500'), month=9, year=2026,
		)

		self.assertEqual(self.client.get(reverse('finance:transaction_edit', args=[other_transaction.pk])).status_code, 404)
		self.assertEqual(self.client.post(reverse('finance:transaction_delete', args=[other_transaction.pk])).status_code, 404)
		self.assertEqual(self.client.get(reverse('finance:budget_edit', args=[other_budget.pk])).status_code, 404)
		self.assertEqual(self.client.post(reverse('finance:budget_delete', args=[other_budget.pk])).status_code, 404)
		self.assertTrue(Transaction.objects.filter(pk=other_transaction.pk).exists())
		self.assertTrue(Budget.objects.filter(pk=other_budget.pk).exists())


class TransactionModelTests(TestCase):
	def test_rejects_category_that_does_not_match_type(self):
		transaction_record = Transaction(
			type=Transaction.Type.INCOME,
			amount=Decimal('2500.00'),
			category='Food',
			description='Groceries',
			payment_method='UPI',
			transaction_date=date(2026, 9, 26),
		)

		with self.assertRaises(ValidationError):
			transaction_record.full_clean()

	def test_rejects_zero_amount(self):
		transaction_record = Transaction(
			type=Transaction.Type.EXPENSE,
			amount=Decimal('0.00'),
			category='Food',
			description='Groceries',
			payment_method='UPI',
			transaction_date=date(2026, 9, 26),
		)

		with self.assertRaises(ValidationError):
			transaction_record.full_clean()


class BudgetModelTests(AuthenticatedFinanceTestCase):
	def test_category_budget_is_unique_per_month(self):
		Budget.objects.create(owner=self.user, category='Food', amount=Decimal('5000'), month=9, year=2026)
		with self.assertRaises(IntegrityError):
			with transaction.atomic():
				Budget.objects.create(owner=self.user, category='Food', amount=Decimal('6000'), month=9, year=2026)


class AnalyticsTests(AuthenticatedFinanceTestCase):
	def test_empty_data_returns_zero_metrics(self):
		metrics = analyze_transactions(Transaction.objects.none(), date(2026, 9, 1), date(2026, 9, 30))

		self.assertEqual(metrics['income'], 0)
		self.assertEqual(metrics['expenses'], 0)
		self.assertEqual(metrics['savings_rate'], 0)
		self.assertEqual(metrics['daily_labels'], [])
		self.assertEqual(metrics['transaction_count'], 0)

	def test_expense_only_period_has_safe_savings_rate_and_pandas_statistics(self):
		Transaction.objects.create(
			type=Transaction.Type.EXPENSE,
			amount=Decimal('100.00'),
			category='Food',
			description='Lunch',
			payment_method='UPI',
			transaction_date=date(2026, 9, 10),
		)
		Transaction.objects.create(
			type=Transaction.Type.EXPENSE,
			amount=Decimal('300.00'),
			category='Food',
			description='Dinner',
			payment_method='Cash',
			transaction_date=date(2026, 9, 12),
		)

		metrics = analyze_transactions(Transaction.objects.all(), date(2026, 9, 1), date(2026, 9, 30))

		self.assertEqual(metrics['savings_rate'], 0)
		self.assertEqual(metrics['savings'], -400)
		self.assertEqual(metrics['average_expense'], 200)
		self.assertEqual(metrics['median_expense'], 200)
		self.assertEqual(metrics['highest_category'], 'Food')
		self.assertEqual(metrics['category_percentages'], [100.0])

	def test_analytics_page_renders_category_daily_and_income_rows(self):
		Transaction.objects.create(
			owner=self.user,
			type='expense', amount=Decimal('100'), category='Food', description='Lunch',
			payment_method='UPI', transaction_date=date(2026, 9, 10),
		)
		Transaction.objects.create(
			owner=self.user,
			type='income', amount=Decimal('900'), category='Salary', description='Payday',
			payment_method='Bank Transfer', transaction_date=date(2026, 9, 10),
		)

		response = self.client.get(reverse('finance:analytics'), {
			'period': 'custom', 'start': '2026-09-01', 'end': '2026-09-30',
		})

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'Food')
		self.assertContains(response, '100.0%')
		self.assertContains(response, 'Sep 10, 2026')
		self.assertContains(response, 'Salary')
		self.assertNotContains(response, '{{')

	def test_invalid_custom_range_falls_back_to_current_month(self):
		bounds = get_date_bounds({'period': 'custom', 'start': '2026-09-20', 'end': '2026-09-01'}, date(2026, 9, 26))

		self.assertEqual(bounds, {'period': 'month', 'start': date(2026, 9, 1), 'end': date(2026, 9, 26)})


class TransactionViewTests(AuthenticatedFinanceTestCase):
	def transaction_data(self, **overrides):
		data = {
			'type': 'expense',
			'amount': '250.00',
			'transaction_date': '2026-09-10',
			'category': 'Food',
			'description': 'Lunch',
			'payment_method': 'UPI',
		}
		data.update(overrides)
		return data

	def test_create_rejects_negative_amount(self):
		response = self.client.post(reverse('finance:transaction_add'), self.transaction_data(amount='-2'))

		self.assertEqual(response.status_code, 200)
		self.assertIn('amount', response.context['form'].errors)
		self.assertEqual(Transaction.objects.count(), 0)

	def test_create_rejects_invalid_date_and_type(self):
		invalid_date = self.client.post(
			reverse('finance:transaction_add'), self.transaction_data(transaction_date='not-a-date')
		)
		self.assertIn('transaction_date', invalid_date.context['form'].errors)

		invalid_type = self.client.post(
			reverse('finance:transaction_add'), self.transaction_data(type='transfer')
		)
		self.assertIn('type', invalid_type.context['form'].errors)
		self.assertEqual(Transaction.objects.count(), 0)

	def test_create_edit_and_delete_transaction(self):
		response = self.client.post(reverse('finance:transaction_add'), self.transaction_data())
		self.assertRedirects(response, reverse('finance:transactions'))
		transaction_record = Transaction.objects.get()

		response = self.client.post(
			reverse('finance:transaction_edit', args=[transaction_record.pk]),
			self.transaction_data(amount='325.00', description='Dinner'),
		)
		self.assertRedirects(response, reverse('finance:transactions'))
		transaction_record.refresh_from_db()
		self.assertEqual(transaction_record.amount, Decimal('325.00'))
		self.assertEqual(transaction_record.description, 'Dinner')

		delete_url = reverse('finance:transaction_delete', args=[transaction_record.pk])
		self.assertEqual(self.client.get(delete_url).status_code, 405)
		response = self.client.post(delete_url)
		self.assertRedirects(response, reverse('finance:transactions'))
		self.assertFalse(Transaction.objects.exists())

	def test_search_filter_sort_and_csv_export(self):
		Transaction.objects.create(owner=self.user, **self.transaction_data())
		Transaction.objects.create(owner=self.user, **self.transaction_data(
			type='income', amount='2500.00', category='Salary', description='Monthly salary'
		))

		response = self.client.get(reverse('finance:transactions'), {'q': 'salary', 'type': 'income'})
		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.context['page'].paginator.count, 1)
		self.assertContains(response, 'Monthly salary')
		self.assertContains(response, '2,500.00')
		self.assertNotContains(response, '{{')
		self.assertNotContains(response, 'Lunch')

		response = self.client.get(reverse('finance:export_transactions'), {'type': 'income'})
		self.assertEqual(response['Content-Type'], 'text/csv; charset=utf-8')
		self.assertIn('Monthly salary', response.content.decode('utf-8-sig'))
		self.assertNotIn('Lunch', response.content.decode('utf-8-sig'))

	def test_dashboard_date_range_drives_calculated_metrics(self):
		Transaction.objects.create(owner=self.user, **self.transaction_data(type='income', amount='1000', category='Salary'))
		Transaction.objects.create(owner=self.user, **self.transaction_data(
			amount='200', transaction_date='2026-08-31', description='Outside selected range'
		))

		response = self.client.get(reverse('finance:dashboard'), {
			'period': 'custom', 'start': '2026-09-01', 'end': '2026-09-30',
		})

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.context['metrics']['income'], 1000)
		self.assertEqual(response.context['metrics']['expenses'], 0)
		self.assertEqual(response.context['metrics']['transaction_count'], 1)
		self.assertContains(response, 'Sep 1')
		self.assertContains(response, 'Sep 30, 2026')
		self.assertContains(response, '1,000.00')
		self.assertNotContains(response, '{{')


class BudgetViewTests(AuthenticatedFinanceTestCase):
	def budget_data(self, amount='1000.00'):
		return {'category': 'Food', 'amount': amount, 'month': '9', 'year': '2026'}

	def test_budget_create_updates_existing_category_month(self):
		url = reverse('finance:budgets')
		self.assertRedirects(self.client.post(url, self.budget_data()), url)
		self.assertRedirects(self.client.post(url, self.budget_data('1200.00')), url)

		self.assertEqual(Budget.objects.count(), 1)
		self.assertEqual(Budget.objects.get().amount, Decimal('1200.00'))

	def test_budget_edit_and_delete(self):
		budget = Budget.objects.create(owner=self.user, category='Food', amount=Decimal('500'), month=9, year=2026)
		edit_url = reverse('finance:budget_edit', args=[budget.pk])
		response = self.client.post(edit_url, self.budget_data('750.00'))
		self.assertRedirects(response, reverse('finance:budgets'))
		budget.refresh_from_db()
		self.assertEqual(budget.amount, Decimal('750.00'))

		delete_url = reverse('finance:budget_delete', args=[budget.pk])
		self.assertEqual(self.client.get(delete_url).status_code, 405)
		self.assertRedirects(self.client.post(delete_url), reverse('finance:budgets'))
		self.assertFalse(Budget.objects.exists())

	def test_budget_status_warns_at_eighty_percent_and_marks_overage(self):
		budget = Budget.objects.create(owner=self.user, category='Food', amount=Decimal('100'), month=9, year=2026)
		Transaction.objects.create(
			owner=self.user,
			type='expense', amount=Decimal('80'), category='Food', description='Groceries',
			payment_method='Cash', transaction_date=date(2026, 9, 12),
		)

		response = self.client.get(reverse('finance:budgets'), {'month': 9, 'year': 2026})
		row = response.context['budget_rows'][0]
		self.assertEqual(row['status'], 'warning')
		self.assertEqual(row['utilization'], 80)

		Transaction.objects.create(
			owner=self.user,
			type='expense', amount=Decimal('30'), category='Food', description='More groceries',
			payment_method='Cash', transaction_date=date(2026, 9, 13),
		)
		response = self.client.get(reverse('finance:budgets'), {'month': 9, 'year': 2026})
		row = response.context['budget_rows'][0]
		self.assertEqual(row['status'], 'exceeded')
		self.assertEqual(row['overage'], Decimal('10'))
from django.test import TestCase

# Create your tests here.
