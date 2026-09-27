# Ledgerly Personal Finance Analytics

A Django expense and income tracker with persistent SQLite storage, Pandas-powered financial analysis, Chart.js visualizations, and monthly category budgets.

## Run locally

Requires Python 3.12 or later.

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Open http://127.0.0.1:8000. The SQLite database is created as `db.sqlite3` in the project root and persists between runs.

## Tests

```powershell
python manage.py test finance
```

## Project structure

- `config/` contains Django project settings and root routes.
- `finance/` contains transaction and budget models, forms, views, URL routes, and Pandas analytics.
- `finance/templates/finance/` contains the server-rendered pages.
- `static/finance/` contains shared CSS and browser-side chart/theme behavior.

The dashboard and analytics pages support today, week, month, last month, year, custom, and all-time date ranges. Transaction CSV exports retain the active search and filter criteria. Chart.js and Lucide icons load from public CDNs, so those visual assets require an internet connection; the Django application and SQLite data remain local.

For deployment, set `DJANGO_SECRET_KEY`, set `DJANGO_DEBUG=false`, and provide `DJANGO_ALLOWED_HOSTS` as a comma-separated list of hostnames. The built-in development key is not suitable for production.
