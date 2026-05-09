"""
Django settings for real_estate_pms project.
"""

import os
from pathlib import Path
from decouple import config
from django.contrib.messages import constants as messages  # moved up
from import_export.formats.base_formats import CSV, XLSX
from django.templatetags.static import static
from django.urls import reverse_lazy

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.1/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = config('SECRET_KEY')

# For development only – in production use a list of allowed domains
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='').split(',') if config('ALLOWED_HOSTS', default='') else ['*']

# Application definition

INSTALLED_APPS = [
    "unfold",                           # replaces jazzmin — must be first
    "unfold.contrib.filters",           # advanced filters
    "unfold.contrib.import_export",     #  ImportExportModelAdmin

    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    "django.contrib.humanize",
    "simple_history",

    "import_export",                    # Export/Import buttons on every list view
    "rangefilter",                      # Date-range sidebar filter
    "admin_confirm",                    # Confirmation step for bulk actions

    'apps.accounts.apps.AccountsConfig',
    'apps.projects_and_plots.apps.ProjectsAndPlotsConfig',
    'apps.customers.apps.CustomersConfig',
    'apps.bookings.apps.BookingsConfig',
    'apps.expenses.apps.ExpensesConfig',
    'apps.reports.apps.ReportsConfig',
    'apps.dashboard',
]

AUTH_USER_MODEL = "accounts.User"

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    "simple_history.middleware.HistoryRequestMiddleware",
]

ROOT_URLCONF = 'config.urls'

# Redirect to dashboard after login
LOGIN_REDIRECT_URL = '/'
# Redirect to login when unauthenticated
LOGIN_URL = '/accounts/login/'

# Django messages maps 'error' tag correctly
MESSAGE_TAGS = {
    messages.ERROR: 'error',
}

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'], 
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'
ASGI_APPLICATION = 'config.asgi.application'

# Database
# https://docs.djangoproject.com/en/5.1/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config('DB_NAME'),
        'USER': config('DB_USER'),
        'PASSWORD': config('DB_PASSWORD'),
        'HOST': config('DB_HOST', default='localhost'),
        'PORT': config('DB_PORT', default='5433'),

        # Optional but recommended performance tweaks
        'ATOMIC_REQUESTS': True,   # Good for most web apps
        'CONN_MAX_AGE': 600,       # Keep connections open for 10 minutes
    }
}

# Password validation
# https://docs.djangoproject.com/en/5.1/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Internationalization setting
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Karachi'  
USE_I18N = True
USE_TZ = True

# Static & media files (MEDIA_URL defined only once)
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# ── Import / Export settings ──────────────────────────────────────
IMPORT_EXPORT_USE_TRANSACTIONS = True
IMPORT_FORMATS = [CSV, XLSX]
EXPORT_FORMATS = [CSV, XLSX]

# ── Unfold admin theme ────────────────────────────────────────────

def environment_callback(request):
    from django.conf import settings as s
    if getattr(s, 'DEBUG', True):
        return ['Development', 'warning']
    return ['Production', 'danger']


def pending_expenses_badge(request):
    try:
        from apps.expenses.models import Expense
        return Expense.objects.filter(is_deleted=False).count() or None
    except Exception:
        return None


UNFOLD = {
    # ── Branding ───────────────────────────────────────────────────
    "SITE_TITLE":     "Royal Land PMS",
    "SITE_HEADER":    "Royal Land PMS",
    "SITE_SUBHEADER": "Property Management System",
    "SITE_URL":       "/",
    "SITE_SYMBOL":    "apartment",

    # ── Environment badge (top-right corner) ───────────────────────
    "ENVIRONMENT":          "config.settings.base.environment_callback",
    "ENVIRONMENT_TITLE_PREFIX": True,

    # ── Dark / Light ───────────────────────────────────────────────
    "DARK_MODE_BUTTON": True,
    "DEFAULT_THEME":    "light",

    # ── Shape ──────────────────────────────────────────────────────
    "BORDER_RADIUS": "6px",
    "DASHBOARD_CALLBACK": "apps.dashboard.views.dashboard_callback",

    # ── Colors: Corporate Blue — trust, authority, precision ───────
    # Primary: Tailwind blue-600 (#2563EB) — professional, trustworthy
    # Base: Tailwind slate — clean neutrals, not harsh grey
    "COLORS": {
           "base": {
        "50":  "248 250 252",
        "100": "241 245 249",
        "200": "226 232 240",
        "300": "203 213 225",
        "400": "148 163 184",
        "500": "100 116 139",
        "600": "71 85 105",
        "700": "51 65 85",
        "800": "30 41 59",
        "900": "15 23 42",
        "950": "2 6 23",
    },
    "primary": {
        "50":  "245 243 255",
        "100": "237 233 254",
        "200": "221 214 254",
        "300": "196 181 253",
        "400": "167 139 250",
        "500": "139 92 246",
        "600": "124 58 237",
        "700": "109 40 217",
        "800": "91 33 182",
        "900": "76 29 149",
        "950": "46 16 101",
    },
        "success": {
            "50":  "240 253 244",
            "100": "220 252 231",
            "200": "187 247 208",
            "300": "134 239 172",
            "400": "74 222 128",
            "500": "34 197 94",
            "600": "22 163 74",
            "700": "21 128 61",
            "800": "22 101 52",
            "900": "20 83 45",
            "950": "5 46 22",
        },
        "info": {
            "50":  "240 249 255",
            "100": "224 242 254",
            "200": "186 230 253",
            "300": "125 211 252",
            "400": "56 189 248",
            "500": "14 165 233",
            "600": "2 132 199",
            "700": "3 105 161",
            "800": "7 89 133",
            "900": "12 74 110",
            "950": "8 47 73",
        },
        "warning": {
            "50":  "255 251 235",
            "100": "254 243 199",
            "200": "253 230 138",
            "300": "252 211 77",
            "400": "251 191 36",
            "500": "245 158 11",
            "600": "217 119 6",
            "700": "180 83 9",
            "800": "146 64 14",
            "900": "120 53 15",
            "950": "69 26 3",
        },
        "danger": {
            "50":  "254 242 242",
            "100": "254 226 226",
            "200": "254 202 202",
            "300": "252 165 165",
            "400": "248 113 113",
            "500": "239 68 68",
            "600": "220 38 38",
            "700": "185 28 28",
            "800": "153 27 27",
            "900": "127 29 29",
            "950": "69 10 10",
        },
    },

    # ── Sidebar ────────────────────────────────────────────────────
    "SIDEBAR": {
        "show_search":           True,
        "show_all_applications": False,
        "navigation": [
            {
                "title": "Overview",
                "separator": False,
                "items": [
                    {
                        "title": "Dashboard",
                        "icon":  "dashboard",
                        "link":  reverse_lazy("admin:index"),
                    },
                ],
            },
            {
                "title": "Users & Auth",
                "separator": True,
                "items": [
                    {
                        "title": "Staff Accounts",
                        "icon":  "manage_accounts",
                        "link":  reverse_lazy("admin:accounts_user_changelist"),
                    },
                ],
            },
            {
                "title": "Property",
                "separator": True,
                "items": [
                    {
                        "title": "Projects",
                        "icon":  "location_city",
                        "link":  reverse_lazy("admin:projects_and_plots_project_changelist"),
                    },
                    {
                        "title": "Plots",
                        "icon":  "map",
                        "link":  reverse_lazy("admin:projects_and_plots_plot_changelist"),
                    },
                ],
            },
            {
                "title": "Sales",
                "separator": True,
                "items": [
                    {
                        "title": "Customers",
                        "icon":  "contacts",
                        "link":  reverse_lazy("admin:customers_customer_changelist"),
                    },
                    {
                        "title": "Bookings",
                        "icon":  "contract",
                        "link":  reverse_lazy("admin:bookings_booking_changelist"),
                    },
                    {
                        "title": "Installments",
                        "icon":  "payments",
                        "link":  reverse_lazy("admin:bookings_installment_changelist"),
                    },
                ],
            },
            {
                "title": "Finance",
                "separator": True,
                "items": [
                    {
                        "title":  "Expenses",
                        "icon":   "receipt_long",
                        "link":   reverse_lazy("admin:expenses_expense_changelist"),
                        "badge":  "config.settings.base.pending_expenses_badge",
                    },
                ],
            },
            {
                "title": "Reports",
                "separator": True,
                "collapsible": True,
                "items": [
                    {
                        "title": "Monthly Payments",
                        "icon":  "calendar_month",
                        "link":  "/reports/monthly-collection/",
                    },
                    {
                        "title": "Money In vs Out",
                        "icon":  "account_balance",
                        "link":  "/reports/cash-flow/",
                    },
                    {
                        "title": "Pending Activations",
                        "icon":  "pending_actions",
                        "link":  "/reports/token-pipeline/",
                    },
                    {
                        "title": "Late Payments",
                        "icon":  "warning",
                        "link":  "/reports/overdue-aging/",
                    },
                    {
                        "title": "Sales by Plan Type",
                        "icon":  "bar_chart",
                        "link":  "/reports/payment-plan-breakdown/",
                    },
                ],
            },
            {
                "title": "Audit & History",
                "separator": True,
                "items": [
                    {
                        "title": "User History",
                        "icon":  "manage_history",
                        "link":  reverse_lazy("admin:accounts_historicaluser_changelist"),
                    },
                    {
                        "title": "Project History",
                        "icon":  "manage_history",
                        "link":  reverse_lazy("admin:projects_and_plots_historicalproject_changelist"),
                    },
                    {
                        "title": "Plot History",
                        "icon":  "manage_history",
                        "link":  reverse_lazy("admin:projects_and_plots_historicalplot_changelist"),
                    },
                    {
                        "title": "Booking History",
                        "icon":  "manage_history",
                        "link":  reverse_lazy("admin:bookings_historicalbooking_changelist"),
                    },
                    {
                        "title": "Installment History",
                        "icon":  "manage_history",
                        "link":  reverse_lazy("admin:bookings_historicalinstallment_changelist"),
                    },
                    {
                        "title": "Expense History",
                        "icon":  "manage_history",
                        "link":  reverse_lazy("admin:expenses_historicalexpense_changelist"),
                    },
                    {
                        "title": "Customer History",
                        "icon":  "manage_history",
                        "link":  reverse_lazy("admin:customers_historicalcustomer_changelist"),
                    },
                ],
            },
        ],
    },
}