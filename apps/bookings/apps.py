# apps/bookings/apps.py

from django.apps import AppConfig


class BookingsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.bookings'

    def ready(self):
        import apps.bookings.signals as _signals  # noqa: F401
        del _signals