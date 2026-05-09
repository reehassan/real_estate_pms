# =============================================================================
# config/settings/production.py — Royal Land PMS
# =============================================================================
# Inherits everything from base.py, then:
#   - Locks down DEBUG, ALLOWED_HOSTS, CSRF origins
#   - Enables all Django security middleware headers
#   - Configures logging to stdout (Docker captures it)
# =============================================================================

from .base import *  # noqa: F401, F403

# ── Core ──────────────────────────────────────────────────────────────────────
DEBUG = False

SECRET_KEY = config('SECRET_KEY')   # must be set in .env.prod — no default

ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='').split(',')

# ── CSRF & session origins ────────────────────────────────────────────────────
# List every origin users will access the site from.
# Example: CSRF_TRUSTED_ORIGINS=https://royalland.pk,https://www.royalland.pk
CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in config('CSRF_TRUSTED_ORIGINS', default='').split(',')
    if origin.strip()
]

# ── HTTPS / Security headers ──────────────────────────────────────────────────
# Django sets these HTTP response headers when running behind Nginx TLS.
# Nginx already sends HSTS — Django's setting also guards direct Gunicorn access.
SECURE_SSL_REDIRECT              = config('SECURE_SSL_REDIRECT', default=True, cast=bool)
SECURE_PROXY_SSL_HEADER          = ('HTTP_X_FORWARDED_PROTO', 'https')

SESSION_COOKIE_SECURE            = True
SESSION_COOKIE_HTTPONLY          = True
SESSION_COOKIE_SAMESITE          = 'Lax'

CSRF_COOKIE_SECURE               = True
CSRF_COOKIE_HTTPONLY             = True
CSRF_COOKIE_SAMESITE             = 'Lax'

SECURE_HSTS_SECONDS              = 31536000   # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS   = True
SECURE_HSTS_PRELOAD              = True
SECURE_CONTENT_TYPE_NOSNIFF      = True
SECURE_BROWSER_XSS_FILTER        = True
X_FRAME_OPTIONS                  = 'DENY'

# ── Database ──────────────────────────────────────────────────────────────────
# Inherited from base.py (reads DB_* from env).
# CONN_MAX_AGE=600 is already set in base — fine for production.

# ── Static / Media ────────────────────────────────────────────────────────────
# Paths inherited from base.py — Nginx serves from named Docker volumes.
STATIC_ROOT = BASE_DIR / 'staticfiles'
MEDIA_ROOT  = BASE_DIR / 'media'

# ── Email (console backend → swap for SMTP / SES in production) ───────────────
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST          = config('EMAIL_HOST',     default='smtp.gmail.com')
EMAIL_PORT          = config('EMAIL_PORT',     default=587,  cast=int)
EMAIL_USE_TLS       = config('EMAIL_USE_TLS',  default=True, cast=bool)
EMAIL_HOST_USER     = config('EMAIL_HOST_USER',    default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
DEFAULT_FROM_EMAIL  = config('DEFAULT_FROM_EMAIL',  default='noreply@royalland.pk')

# ── Remove debug-only apps ────────────────────────────────────────────────────
INSTALLED_APPS = [app for app in INSTALLED_APPS if app not in (
    'debug_toolbar',
)]

MIDDLEWARE = [m for m in MIDDLEWARE if 'debug_toolbar' not in m]

# ── Logging — structured stdout for Docker / Hetzner ─────────────────────────
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{asctime} {levelname} {name} {message}',
            'style':  '{',
        },
    },
    'handlers': {
        'console': {
            'class':     'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level':    'WARNING',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level':    config('DJANGO_LOG_LEVEL', default='WARNING'),
            'propagate': False,
        },
        'django.security': {
            'handlers':  ['console'],
            'level':     'ERROR',
            'propagate': False,
        },
        # App-level: set to INFO so booking/signal events are visible
        'apps': {
            'handlers':  ['console'],
            'level':     'INFO',
            'propagate': False,
        },
    },
}