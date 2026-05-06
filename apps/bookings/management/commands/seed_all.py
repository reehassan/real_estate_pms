"""
Seed command to populate the Royal Land PMS with American-themed test data.
Run:   python manage.py seed_all
"""

from django.core.management.base import BaseCommand
from decimal import Decimal
from datetime import timedelta, date
import random

from apps.accounts.models import User
from apps.projects_and_plots.models import Project, Plot
from apps.customers.models import Customer
from apps.bookings.models import Booking, Installment
from apps.bookings.services.installment_service import generate_installments
from apps.expenses.models import Expense


class Command(BaseCommand):
    help = "Seeds the database with American-themed demo data"

    def handle(self, *args, **options):
        self.stdout.write("🌱 Seeding database...")

        # ── 1. Users ─────────────────────────────────────────
        admin_user, created = User.objects.get_or_create(
            username="admin",
            defaults={
                "email": "admin@royalland.com",
                "first_name": "George",
                "last_name": "Washington",
                "is_staff": True,
                "is_superuser": True,
            }
        )
        admin_user.set_password("admin123")
        admin_user.save()

        staff_user, _ = User.objects.get_or_create(
            username="staff",
            defaults={
                "email": "staff@royalland.com",
                "first_name": "Thomas",
                "last_name": "Jefferson",
                "is_staff": True,
                "is_superuser": False,
            }
        )
        staff_user.set_password("staff123")
        staff_user.save()

        self.stdout.write(f"  ✅ Users: admin / admin123, staff / staff123")

        # ── 2. Projects ───────────────────────────────────────
        project_data = [
            {"name": "Lexington Estates", "code": "LEX", "location": "Boston, MA",
             "total_plots": 20, "total_area": 500, "area_unit": "Marla", "status": "ACTIVE"},
            {"name": "Concord Green", "code": "CON", "location": "Philadelphia, PA",
             "total_plots": 15, "total_area": 350, "area_unit": "Marla", "status": "ACTIVE"},
            {"name": "Yorktown Heights", "code": "YRK", "location": "New York, NY",
             "total_plots": 25, "total_area": 600, "area_unit": "Marla", "status": "ACTIVE"},
            {"name": "Jamestown Villas", "code": "JAM", "location": "Richmond, VA",
             "total_plots": 10, "total_area": 200, "area_unit": "Marla", "status": "PLANNING"},
            {"name": "Plymouth Colony", "code": "PLY", "location": "Plymouth, MA",
             "total_plots": 30, "total_area": 800, "area_unit": "Marla", "status": "ACTIVE"},
        ]

        projects = []                         # <-- list persists for later use
        for pdata in project_data:
            proj, _ = Project.objects.get_or_create(
                code=pdata["code"],
                defaults={
                    "name": pdata["name"],
                    "location": pdata["location"],
                    "total_plots": pdata["total_plots"],
                    "total_area": pdata["total_area"],
                    "area_unit": pdata["area_unit"],
                    "status": pdata["status"],
                }
            )
            projects.append(proj)
        self.stdout.write(f"  ✅ Projects: {len(projects)} created")

        # ── 3. Plots ──────────────────────────────────────────
        plot_statuses = ["AVAILABLE", "BOOKED", "SOLD"]
        plot_categories = ["Residential", "Commercial"]
        plot_sizes = [3, 5, 10, 20]  # Marla
        plot_prices = [1500000, 2500000, 5000000, 7500000]

        for proj in projects:
            for n in range(1, proj.total_plots + 1):
                plot_num = f"{100 + n}" if n < 10 else str(100 + n)
                Plot.objects.get_or_create(
                    project=proj,
                    plot_number=plot_num,
                    defaults={
                        "block": chr(65 + (n-1)//5),
                        "size": random.choice(plot_sizes),
                        "size_unit": "Marla",
                        "category": random.choice(plot_categories),
                        "price": random.choice(plot_prices),
                        "status": random.choice(plot_statuses),
                    }
                )
        all_plots = Plot.objects.all()
        self.stdout.write(f"  ✅ Plots: {all_plots.count()} created")

        # ── 4. Customers ──────────────────────────────────────
        customer_names = [
            ("John", "Smith"), ("Mary", "Johnson"), ("Robert", "Williams"),
            ("Patricia", "Brown"), ("James", "Jones"), ("Linda", "Garcia"),
            ("Michael", "Miller"), ("Barbara", "Davis"), ("William", "Rodriguez"),
            ("Elizabeth", "Martinez"),
        ]
        customers = []
        for fname, lname in customer_names:
            cust, _ = Customer.objects.get_or_create(
                cnic=f"US-{1000000000 + len(customers)}",
                defaults={
                    "full_name": f"{fname} {lname}",
                    "phone": f"+1-555-{random.randint(1000,9999)}",
                    "address": f"{random.randint(100,999)} Main St, {fname}'s City",
                }
            )
            customers.append(cust)
        self.stdout.write(f"  ✅ Customers: {len(customers)} created")

        # ── 5. Bookings (with installments) ───────────────────
        booked_plots = all_plots.filter(status="BOOKED")[:8]
        plan_choices = [Booking.PaymentPlan.THREE_YEAR, Booking.PaymentPlan.FIVE_YEAR]
        self.stdout.write(f"  📦 Creating bookings for {booked_plots.count()} plots...")

        for plot in booked_plots:
            if Booking.objects.filter(plot=plot, status="active", is_deleted=False).exists():
                continue

            customer = random.choice(customers)
            total_price = Decimal(plot.price)
            down_payment = total_price * Decimal('0.20')
            booking_date = date.today() - timedelta(days=random.randint(30, 180))

            booking = Booking.objects.create(
                customer=customer,
                plot=plot,
                booked_by=staff_user,
                booking_date=booking_date,
                total_price=total_price,
                down_payment=down_payment,
                payment_plan=random.choice(plan_choices),
                status=Booking.Status.ACTIVE,
            )
            if not booking.installments.exists():
                generate_installments(booking)

        completed_booking = Booking.objects.filter(status="active").first()
        if completed_booking:
            completed_booking.status = Booking.Status.COMPLETED
            completed_booking.save()
            for inst in completed_booking.installments.all():
                inst.amount_paid = inst.amount_due
                inst.paid_on = date.today()
                inst.status = Installment.Status.PAID
                inst.save()

        self.stdout.write(f"  ✅ Bookings: {Booking.objects.count()} created")

        # ── 6. Expenses ───────────────────────────────────────
        expense_categories = ["Land", "Construction", "Marketing", "Utilities", "Miscellaneous"]
        for i in range(20):
            Expense.objects.create(
                description=f"Expense #{i+1}: {random.choice(expense_categories)}",
                amount=random.randint(50000, 500000),
                category=random.choice(expense_categories),
                date=date.today() - timedelta(days=random.randint(10, 300)),
                project=random.choice(projects),    # <-- uses the `projects` list from step 2
            )
        self.stdout.write(f"  ✅ Expenses: {Expense.objects.count()} created")

        self.stdout.write(self.style.SUCCESS("🎉 Seed data loaded successfully!"))