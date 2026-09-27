import csv
from datetime import date
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_POST

from .analytics import analyze_transactions, get_date_bounds
from .forms import BudgetForm, TransactionForm
from .models import Budget, CATEGORY_CHOICES, Transaction


@login_required
def dashboard(request):
    bounds = get_date_bounds(request.GET, timezone.localdate())
    transactions = Transaction.objects.filter(
        owner=request.user,
        transaction_date__range=(bounds['start'], bounds['end']),
    )
    metrics = analyze_transactions(transactions, bounds['start'], bounds['end'])
    today = timezone.localdate()
    current_month = Transaction.objects.filter(
        owner=request.user,
        transaction_date__year=today.year,
        transaction_date__month=today.month,
    )
    month_income = current_month.filter(type=Transaction.Type.INCOME).aggregate(total=Sum('amount'))['total'] or Decimal('0')
    month_expenses = current_month.filter(type=Transaction.Type.EXPENSE).aggregate(total=Sum('amount'))['total'] or Decimal('0')
    recent = transactions.order_by('-transaction_date', '-created_at')[:6]
    budget_rows = budget_status(request.user, today.month, today.year)
    return render(request, 'finance/dashboard.html', {
        'metrics': metrics,
        'bounds': bounds,
        'recent_transactions': recent,
        'month_income': month_income,
        'month_expenses': month_expenses,
        'budget_rows': budget_rows[:4],
        'chart_metrics': metrics,
    })


def transaction_queryset(params, owner):
    queryset = Transaction.objects.filter(owner=owner)
    search = params.get('q', '').strip()
    transaction_type = params.get('type', '')
    category = params.get('category', '')
    month = params.get('month', '')
    sort = params.get('sort', 'newest')

    if search:
        query = Q(description__icontains=search) | Q(category__icontains=search) | Q(payment_method__icontains=search)
        try:
            query |= Q(amount=Decimal(search))
        except InvalidOperation:
            pass
        queryset = queryset.filter(query)
    if transaction_type in Transaction.Type.values:
        queryset = queryset.filter(type=transaction_type)
    if category in dict(CATEGORY_CHOICES):
        queryset = queryset.filter(category=category)
    parsed_month = parse_date(f'{month}-01') if len(month) == 7 else None
    if parsed_month:
        queryset = queryset.filter(transaction_date__year=parsed_month.year, transaction_date__month=parsed_month.month)

    sort_fields = {
        'newest': '-transaction_date',
        'oldest': 'transaction_date',
        'amount-high': '-amount',
        'amount-low': 'amount',
    }
    queryset = queryset.order_by(sort_fields.get(sort, '-transaction_date'), '-created_at')
    filters = {'q': search, 'type': transaction_type, 'category': category, 'month': month, 'sort': sort}
    return queryset, filters


@login_required
def transaction_list(request):
    queryset, filters = transaction_queryset(request.GET, request.user)
    page = Paginator(queryset, 12).get_page(request.GET.get('page'))
    return render(request, 'finance/transactions.html', {
        'page': page,
        'filters': filters,
        'categories': CATEGORY_CHOICES,
        'transaction_types': Transaction.Type.choices,
    })


@login_required
def transaction_create(request):
    form = TransactionForm(request.POST or None, initial={'transaction_date': timezone.localdate()})
    if request.method == 'POST' and form.is_valid():
        transaction_record = form.save(commit=False)
        transaction_record.owner = request.user
        transaction_record.save()
        messages.success(request, 'Transaction added.')
        return redirect('finance:transactions')
    return render(request, 'finance/transaction_form.html', {'form': form, 'page_title': 'Add transaction'})


@login_required
def transaction_update(request, pk):
    transaction_record = get_object_or_404(Transaction, pk=pk, owner=request.user)
    form = TransactionForm(request.POST or None, instance=transaction_record)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Transaction updated.')
        return redirect('finance:transactions')
    return render(request, 'finance/transaction_form.html', {
        'form': form,
        'page_title': 'Edit transaction',
        'transaction': transaction_record,
    })


@require_POST
@login_required
def transaction_delete(request, pk):
    transaction_record = get_object_or_404(Transaction, pk=pk, owner=request.user)
    transaction_record.delete()
    messages.success(request, 'Transaction deleted.')
    return redirect('finance:transactions')


@login_required
def export_transactions(request):
    transactions, _ = transaction_queryset(request.GET, request.user)
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="transactions.csv"'
    response.write('\ufeff')
    writer = csv.writer(response)
    writer.writerow(['Date', 'Type', 'Amount', 'Category', 'Description', 'Payment method'])
    for transaction_record in transactions.iterator():
        writer.writerow([
            transaction_record.transaction_date.isoformat(),
            transaction_record.get_type_display(),
            transaction_record.amount,
            transaction_record.category,
            transaction_record.description,
            transaction_record.payment_method,
        ])
    return response


@login_required
def analytics_dashboard(request):
    bounds = get_date_bounds(request.GET, timezone.localdate())
    metrics = analyze_transactions(
        Transaction.objects.filter(
            owner=request.user,
            transaction_date__range=(bounds['start'], bounds['end']),
        ),
        bounds['start'],
        bounds['end'],
    )
    return render(request, 'finance/analytics.html', {'metrics': metrics, 'bounds': bounds})


def budget_status(owner, month, year):
    budgets = Budget.objects.filter(owner=owner, month=month, year=year)
    rows = []
    for budget in budgets:
        spent = Transaction.objects.filter(
            owner=owner,
            type=Transaction.Type.EXPENSE,
            category=budget.category,
            transaction_date__year=year,
            transaction_date__month=month,
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        utilization = float(spent / budget.amount * 100) if budget.amount else 0
        status = 'exceeded' if utilization > 100 else 'warning' if utilization >= 80 else 'normal'
        rows.append({
            'budget': budget,
            'spent': spent,
            'remaining': budget.amount - spent,
            'overage': max(spent - budget.amount, Decimal('0')),
            'utilization': min(round(utilization, 1), 100),
            'actual_utilization': round(utilization, 1),
            'status': status,
        })
    return rows


@login_required
def budgets(request):
    today = timezone.localdate()
    budget_instance = None
    if request.method == 'POST':
        try:
            budget_instance = Budget.objects.filter(
                owner=request.user,
                category=request.POST.get('category', ''),
                month=int(request.POST.get('month', '')),
                year=int(request.POST.get('year', '')),
            ).first()
        except (TypeError, ValueError):
            pass
    form = BudgetForm(
        request.POST if request.method == 'POST' else None,
        instance=budget_instance,
        initial={'month': today.month, 'year': today.year},
    )
    if request.method == 'POST' and form.is_valid():
        budget = form.save(commit=False)
        budget.owner = request.user
        budget.save()
        messages.success(request, 'Budget saved.')
        return redirect('finance:budgets')
    selected_month = request.GET.get('month', str(today.month))
    selected_year = request.GET.get('year', str(today.year))
    try:
        month_number, year_number = int(selected_month), int(selected_year)
        if not 1 <= month_number <= 12 or not 2000 <= year_number <= 9999:
            raise ValueError
    except ValueError:
        month_number, year_number = today.month, today.year
    return render(request, 'finance/budgets.html', {
        'form': form,
        'budget_rows': budget_status(request.user, month_number, year_number),
        'selected_month': month_number,
        'selected_year': year_number,
        'month_name': date(year_number, month_number, 1).strftime('%B %Y'),
    })


@login_required
def budget_update(request, pk):
    budget = get_object_or_404(Budget, pk=pk, owner=request.user)
    form = BudgetForm(request.POST or None, instance=budget)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Budget updated.')
        return redirect('finance:budgets')
    return render(request, 'finance/budgets.html', {
        'form': form,
        'budget_rows': budget_status(request.user, budget.month, budget.year),
        'selected_month': budget.month,
        'selected_year': budget.year,
        'month_name': date(budget.year, budget.month, 1).strftime('%B %Y'),
        'editing_budget': budget,
    })


@require_POST
@login_required
def budget_delete(request, pk):
    budget = get_object_or_404(Budget, pk=pk, owner=request.user)
    budget.delete()
    messages.success(request, 'Budget deleted.')
    return redirect('finance:budgets')
