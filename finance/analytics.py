from datetime import date, timedelta

import pandas as pd
from django.utils.dateparse import parse_date


def get_date_bounds(params, today=None):
    today = today or date.today()
    period = params.get('period', 'month')

    if period == 'today':
        start = end = today
    elif period == 'week':
        start = today - timedelta(days=today.weekday())
        end = today
    elif period == 'last_month':
        this_month = today.replace(day=1)
        end = this_month - timedelta(days=1)
        start = end.replace(day=1)
    elif period == 'year':
        start, end = date(today.year, 1, 1), today
    elif period == 'custom':
        start = parse_date(params.get('start', ''))
        end = parse_date(params.get('end', ''))
        if not start or not end or start > end:
            period = 'month'
            start = today.replace(day=1)
            end = today
    elif period == 'all':
        start, end = date(2000, 1, 1), today
    else:
        period = 'month'
        start = today.replace(day=1)
        end = today

    return {'period': period, 'start': start, 'end': end}


def analyze_transactions(transactions, start, end):
    frame = pd.DataFrame.from_records(
        transactions.values('type', 'amount', 'category', 'description', 'transaction_date')
    )
    if frame.empty:
        frame = pd.DataFrame(columns=['type', 'amount', 'category', 'description', 'transaction_date'])
    else:
        frame['amount'] = pd.to_numeric(frame['amount'])
        frame['transaction_date'] = pd.to_datetime(frame['transaction_date'])
        frame['month'] = frame['transaction_date'].dt.to_period('M')

    income_frame = frame[frame['type'] == 'income']
    expense_frame = frame[frame['type'] == 'expense']
    income = float(income_frame['amount'].sum()) if not income_frame.empty else 0.0
    expenses = float(expense_frame['amount'].sum()) if not expense_frame.empty else 0.0
    savings = income - expenses
    savings_rate = (savings / income * 100) if income else 0.0
    month_count = (end.year - start.year) * 12 + end.month - start.month + 1

    months = pd.period_range(start=start.strftime('%Y-%m'), end=end.strftime('%Y-%m'), freq='M')
    monthly_income = []
    monthly_expenses = []
    monthly_savings = []
    monthly_labels = []
    for month in months:
        month_rows = frame[frame['month'] == month] if not frame.empty else frame
        month_income = float(month_rows.loc[month_rows['type'] == 'income', 'amount'].sum())
        month_expenses = float(month_rows.loc[month_rows['type'] == 'expense', 'amount'].sum())
        monthly_labels.append(month.strftime('%b %Y'))
        monthly_income.append(round(month_income, 2))
        monthly_expenses.append(round(month_expenses, 2))
        monthly_savings.append(round(month_income - month_expenses, 2))

    category_totals = expense_frame.groupby('category')['amount'].sum().sort_values(ascending=False)
    category_labels = category_totals.index.tolist()
    category_amounts = [round(float(value), 2) for value in category_totals.tolist()]
    category_percentages = [round(value / expenses * 100, 1) if expenses else 0 for value in category_amounts]
    category_rows = [
        {'category': label, 'amount': amount, 'percentage': percentage}
        for label, amount, percentage in zip(category_labels, category_amounts, category_percentages)
    ]
    if expense_frame.empty:
        daily_totals = pd.Series(dtype='float64')
    else:
        daily_totals = expense_frame.groupby(expense_frame['transaction_date'].dt.date)['amount'].sum().sort_index()
    daily_rows = [
        {'date': day, 'amount': round(float(value), 2)}
        for day, value in daily_totals.items()
    ]
    income_source_totals = income_frame.groupby('category')['amount'].sum().sort_values(ascending=False)

    def expense_summary(row):
        if row is None:
            return None
        return {
            'description': row['description'],
            'category': row['category'],
            'date': row['transaction_date'].date().isoformat(),
            'amount': round(float(row['amount']), 2),
        }

    high_expense = expense_summary(expense_frame.loc[expense_frame['amount'].idxmax()]) if not expense_frame.empty else None
    low_expense = expense_summary(expense_frame.loc[expense_frame['amount'].idxmin()]) if not expense_frame.empty else None
    highest_category = category_labels[0] if category_labels else 'No expenses yet'

    return {
        'income': round(income, 2),
        'expenses': round(expenses, 2),
        'balance': round(savings, 2),
        'savings': round(savings, 2),
        'savings_rate': round(savings_rate, 1),
        'average_monthly_spending': round(expenses / month_count, 2) if month_count else 0,
        'average_expense': round(float(expense_frame['amount'].mean()), 2) if not expense_frame.empty else 0,
        'median_expense': round(float(expense_frame['amount'].median()), 2) if not expense_frame.empty else 0,
        'highest_category': highest_category,
        'transaction_count': len(frame),
        'high_expense': high_expense,
        'low_expense': low_expense,
        'category_labels': category_labels,
        'category_amounts': category_amounts,
        'category_percentages': category_percentages,
        'category_rows': category_rows,
        'daily_labels': [day.isoformat() for day in daily_totals.index],
        'daily_amounts': [round(float(value), 2) for value in daily_totals.tolist()],
        'daily_rows': daily_rows,
        'monthly_labels': monthly_labels,
        'monthly_income': monthly_income,
        'monthly_expenses': monthly_expenses,
        'monthly_savings': monthly_savings,
        'income_source_labels': income_source_totals.index.tolist(),
        'income_source_amounts': [round(float(value), 2) for value in income_source_totals.tolist()],
        'income_sources': [
            {'category': label, 'amount': round(float(value), 2)}
            for label, value in income_source_totals.items()
        ],
    }