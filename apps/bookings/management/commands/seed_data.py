"""
apps/bookings/management/commands/seed_data.py

Seed script for development and testing.
Creates: 1 project, 10 plots, 3 customers, 2 bookings with installments.
Expenses skipped — model not built yet.

Usage:
    python manage.py seed_data
    python manage.py seed_data --flush   # wipe existing seed data first
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from datetime import date 

from apps.projects_and_plots.models import Project, Plot
from apps.customers.models import Customer
from apps.bookings.models import Booking



class Command(BaseCommand):
    help = 'Seed database with development data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--flush',
            action='store_true',
            help='Delete existing seed data before seeding',
        )

    def handle(self, *args, **options):
        if options['flush']:
            self.stdout.write('Flushing existing data...')
            Booking.all_objects.all().delete()
            Customer.all_objects.all().delete()
            Plot.all_objects.all().delete()
            Project.all_objects.all().delete()
            self.stdout.write(self.style.WARNING('Existing data deleted.'))

        with transaction.atomic():
            self._create_project_and_plots()
            self._create_customers()
            self._create_bookings()

        self.stdout.write(self.style.SUCCESS('Seed data created successfully.'))

    # ─────────────────────────────────────────────
    # PRIVATE METHODS
    # ─────────────────────────────────────────────

    def _create_project_and_plots(self):
        self.stdout.write('Creating project...')

        self.project = Project.objects.create(
            name        = 'Dreamland Phase 1',
            location    = 'Bahria Town Road, Rawalpindi',
            total_area  = 500,
            area_unit   = Project.AreaUnit.MARLA,
            description = 'First phase of Dreamland housing scheme.',
            status      = Project.Status.ACTIVE,
        )

        self.stdout.write('Creating 10 plots...')

        plots_data = [
            ('A-01', 'Block A', 5,  Plot.SizeUnit.MARLA, Plot.Category.RESIDENTIAL,  2500000,  Plot.Status.AVAILABLE),
            ('A-02', 'Block A', 5,  Plot.SizeUnit.MARLA, Plot.Category.RESIDENTIAL,  2500000,  Plot.Status.AVAILABLE),
            ('A-03', 'Block A', 10, Plot.SizeUnit.MARLA, Plot.Category.RESIDENTIAL,  4800000,  Plot.Status.AVAILABLE),
            ('A-04', 'Block A', 10, Plot.SizeUnit.MARLA, Plot.Category.RESIDENTIAL,  4800000,  Plot.Status.AVAILABLE),
            ('B-01', 'Block B', 5,  Plot.SizeUnit.MARLA, Plot.Category.RESIDENTIAL,  2700000,  Plot.Status.AVAILABLE),
            ('B-02', 'Block B', 5,  Plot.SizeUnit.MARLA, Plot.Category.RESIDENTIAL,  2700000,  Plot.Status.AVAILABLE),
            ('B-03', 'Block B', 1,  Plot.SizeUnit.KANAL, Plot.Category.RESIDENTIAL,  9500000,  Plot.Status.AVAILABLE),
            ('B-04', 'Block B', 1,  Plot.SizeUnit.KANAL, Plot.Category.RESIDENTIAL,  9500000,  Plot.Status.AVAILABLE),
            ('C-01', 'Block C', 4,  Plot.SizeUnit.MARLA, Plot.Category.COMMERCIAL,   6000000,  Plot.Status.AVAILABLE),
            ('C-02', 'Block C', 4,  Plot.SizeUnit.MARLA, Plot.Category.COMMERCIAL,   6000000,  Plot.Status.AVAILABLE),
        ]

        self.plots = []
        for plot_number, block, size, size_unit, category, price, status in plots_data:
            plot = Plot.objects.create(
                project     = self.project,
                plot_number = plot_number,
                block       = block,
                size        = size,
                size_unit   = size_unit,
                category    = category,
                price       = price,
                status      = status,
            )
            self.plots.append(plot)

        self.stdout.write(f'  Created project: {self.project.name}')
        self.stdout.write(f'  Created {len(self.plots)} plots')

    def _create_customers(self):
        self.stdout.write('Creating 3 customers...')

        customers_data = [
            ('Muhammad Ali Khan',   '35201-1234567-1', '03001234567', 'House 12, Street 4, G-9, Islamabad',    Customer.CustomerType.INDIVIDUAL),
            ('Fatima Sheikh',       '35202-7654321-2', '03217654321', 'Flat 3B, Blue Towers, F-10, Islamabad', Customer.CustomerType.INDIVIDUAL),
            ('Pak Builders Ltd',    '35203-1122334-3', '03451122334', 'Office 5, Business Square, I-8, Islamabad', Customer.CustomerType.CORPORATE),
        ]

        self.customers = []
        for full_name, cnic, phone, address, customer_type in customers_data:
            customer = Customer.objects.create(
                full_name     = full_name,
                cnic          = cnic,
                phone         = phone,
                address       = address,
                customer_type = customer_type,
            )
            self.customers.append(customer)
            self.stdout.write(f'  Created customer: {customer.full_name}')

    def _create_bookings(self):
        self.stdout.write('Creating 2 bookings...')

        from apps.accounts.models import User
        admin_user = User.objects.filter(is_superuser=True).first()

        if not admin_user:
            self.stdout.write(self.style.ERROR(
                'No superuser found. Run: python manage.py createsuperuser first.'
            ))
            return

        # Booking 1 — 3 year plan
        booking1 = Booking.objects.create(
            customer     = self.customers[0],
            plot         = self.plots[0],
            booked_by    = admin_user,
            booking_date = date(2026, 4, 1),
            total_price  = self.plots[0].price,
            down_payment = 500000,
            payment_plan = Booking.PaymentPlan.THREE_YEAR,
            status       = Booking.Status.ACTIVE,
            notes        = 'Seed booking — 3 year plan.',
        )
        self.plots[0].status = Plot.Status.BOOKED
        self.plots[0].save()

        # Booking 2 — 5 year plan
        booking2 = Booking.objects.create(
            customer     = self.customers[1],
            plot         = self.plots[2],
            booked_by    = admin_user,
            booking_date = date(2026, 4, 15),
            total_price  = self.plots[2].price,
            down_payment = 800000,
            payment_plan = Booking.PaymentPlan.FIVE_YEAR,
            status       = Booking.Status.ACTIVE,
            notes        = 'Seed booking — 5 year plan.',
        )
        self.plots[2].status = Plot.Status.BOOKED
        self.plots[2].save()

        self.stdout.write(f'  Booking 1: {booking1} — {booking1.installments.count()} installments')
        self.stdout.write(f'  Booking 2: {booking2} — {booking2.installments.count()} installments')