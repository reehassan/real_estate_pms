"""
apps/bookings/management/commands/seed_all.py

Seed command for Royal Land PMS test data.
Run: python manage.py seed_all

Fixes vs original:
    - CNIC format matches validator  (XXXXX-XXXXXXX-X)
    - Phone format is Pakistani
    - Expense categories match model choices (lowercase)
    - Expense payment_method is required — now included
    - Booking token_amount / token_received_on / down_payment_received_on added
    - Booking status filter uses uppercase (ACTIVE not active)
    - Installment status uses model constants not raw strings
"""

import random
from datetime import date, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand

from apps.accounts.models import User
from apps.bookings.models import Booking, Installment
from apps.bookings.services.installment_service import generate_installments
from apps.customers.models import Customer
from apps.expenses.models import Expense
from apps.projects_and_plots.models import Plot, Project


class Command(BaseCommand):
    help = "Seeds the database with demo data"

    def handle(self, *args, **options):
        self.stdout.write("Seeding database...")

        # ── 1. Users ──────────────────────────────────────────────
        admin_user, _ = User.objects.get_or_create(
            username="admin",
            defaults={
                "email":        "admin@royalland.com",
                "first_name":   "Ahmed",
                "last_name":    "Khan",
                "is_staff":     True,
                "is_superuser": True,
            },
        )
        admin_user.set_password("admin123")
        admin_user.save()

        staff_user, _ = User.objects.get_or_create(
            username="staff",
            defaults={
                "email":        "staff@royalland.com",
                "first_name":   "Sara",
                "last_name":    "Ali",
                "is_staff":     True,
                "is_superuser": False,
            },
        )
        staff_user.set_password("staff123")
        staff_user.save()

        self.stdout.write("  Users: admin / admin123, staff / staff123")

        # ── 2. Projects ───────────────────────────────────────────
        project_data = [
            {
                "name": "Royal Bahria Scheme",    "code": "RBS",
                "location": "Lahore, Punjab",     "total_plots": 20,
                "total_area": 500,  "area_unit": "MARLA", "status": "ACTIVE",
            },
            {
                "name": "Green Valley Heights",   "code": "GVH",
                "location": "Islamabad, Capital", "total_plots": 15,
                "total_area": 350,  "area_unit": "MARLA", "status": "ACTIVE",
            },
            {
                "name": "DHA Villas Rawalpindi",  "code": "DVR",
                "location": "Rawalpindi, Punjab", "total_plots": 25,
                "total_area": 600,  "area_unit": "MARLA", "status": "ACTIVE",
            },
            {
                "name": "Gulshan-e-Iqbal Phase 2","code": "GEI",
                "location": "Karachi, Sindh",     "total_plots": 10,
                "total_area": 200,  "area_unit": "MARLA", "status": "PLANNING",
            },
            {
                "name": "Model Town Extension",   "code": "MTE",
                "location": "Lahore, Punjab",     "total_plots": 30,
                "total_area": 800,  "area_unit": "MARLA", "status": "ACTIVE",
            },
        ]

        projects = []
        for d in project_data:
            proj, _ = Project.objects.get_or_create(
                code=d["code"],
                defaults={k: v for k, v in d.items() if k != "code"},
            )
            projects.append(proj)
        self.stdout.write(f"  Projects: {len(projects)} created")

        # ── 3. Plots ──────────────────────────────────────────────
        plot_statuses  = ["AVAILABLE", "AVAILABLE", "BOOKED", "SOLD"]  # weight available
        plot_sizes     = [Decimal("3"), Decimal("5"), Decimal("10"), Decimal("20")]
        plot_prices    = [1_500_000, 2_500_000, 5_000_000, 7_500_000]

        for proj in projects:
            for n in range(1, proj.total_plots + 1):
                plot_num = str(100 + n)
                Plot.objects.get_or_create(
                    project=proj,
                    plot_number=plot_num,
                    defaults={
                        "block":    chr(65 + (n - 1) // 5),
                        "size":     random.choice(plot_sizes),
                        "size_unit":"MARLA",
                        "category": random.choice(["RESIDENTIAL", "COMMERCIAL"]),
                        "price":    Decimal(random.choice(plot_prices)),
                        "status":   random.choice(plot_statuses),
                    },
                )

        all_plots = Plot.objects.all()
        self.stdout.write(f"  Plots: {all_plots.count()} created")

        # ── 4. Customers ──────────────────────────────────────────
        # CNIC must match validator: XXXXX-XXXXXXX-X
        customer_data = [
            ("Muhammad Ali",      "35202-1234567-1", "03001234567"),
            ("Fatima Khan",       "35202-2345678-2", "03012345678"),
            ("Usman Ahmed",       "42301-3456789-3", "03023456789"),
            ("Ayesha Siddiqui",   "35202-4567890-4", "03034567890"),
            ("Bilal Chaudhry",    "61101-5678901-5", "03045678901"),
            ("Zainab Malik",      "35202-6789012-6", "03056789012"),
            ("Hassan Raza",       "42301-7890123-7", "03067890123"),
            ("Sana Mirza",        "35202-8901234-8", "03078901234"),
            ("Imran Sheikh",      "61101-9012345-9", "03089012345"),
            ("Nadia Baig",        "35202-0123456-0", "03090123456"),
        ]

        customers = []
        for full_name, cnic, phone in customer_data:
            cust, _ = Customer.objects.get_or_create(
                cnic=cnic,
                defaults={
                    "full_name":     full_name,
                    "phone":         phone,
                    "address":       f"House 12, Street 4, {full_name.split()[1]} Colony",
                    "customer_type": "INDIVIDUAL",
                },
            )
            customers.append(cust)
        self.stdout.write(f"  Customers: {len(customers)} created")

        # ── 5. Bookings (with installments) ───────────────────────
        booked_plots = list(Plot.objects.filter(status="BOOKED")[:8])
        plan_choices = [
            Booking.PaymentPlan.ONE_YEAR,
            Booking.PaymentPlan.TWO_YEAR,
            Booking.PaymentPlan.THREE_YEAR,
            Booking.PaymentPlan.FIVE_YEAR,
        ]

        for plot in booked_plots:
            # Skip if an active/token booking already exists
            if Booking.objects.filter(
                plot=plot,
                status__in=[Booking.Status.ACTIVE, Booking.Status.TOKEN],
                is_deleted=False,
            ).exists():
                continue

            customer        = random.choice(customers)
            total_price     = plot.price
            token_amount    = (total_price * Decimal("0.05")).quantize(Decimal("0.01"))
            down_payment    = (total_price * Decimal("0.15")).quantize(Decimal("0.01"))
            booking_date    = date.today() - timedelta(days=random.randint(30, 180))
            token_date      = booking_date
            dp_date         = booking_date + timedelta(days=14)

            booking = Booking.objects.create(
                customer                  = customer,
                plot                      = plot,
                booked_by                 = staff_user,
                booking_date              = booking_date,
                total_price               = total_price,
                token_amount              = token_amount,
                token_received_on         = token_date,
                down_payment              = down_payment,
                down_payment_received_on  = dp_date,
                payment_plan              = random.choice(plan_choices),
                status                    = Booking.Status.ACTIVE,
            )
            generate_installments(booking)

        # Mark one booking as completed with all installments paid
        first = Booking.objects.filter(status=Booking.Status.ACTIVE).first()
        
        if first:
            first.status = Booking.Status.COMPLETED
            first.save(update_fields=["status", "updated_at"])
            today = date.today()
            for inst in first.installments.all():
                inst.amount_paid = inst.amount_due
                inst.paid_on     = today - timedelta(days=random.randint(1, 30))
                inst.status      = Installment.Status.PAID
                inst.save(update_fields=["amount_paid", "paid_on", "status"])

        # Mark some installments as overdue
        overdue_candidates = Installment.objects.filter(status=Installment.Status.PENDING
            , due_date__lt=date.today()
        )[:5]
        for inst in overdue_candidates:
            inst.status = Installment.Status.OVERDUE
            inst.save(update_fields=["status"])

        self.stdout.write(f"  Bookings: {Booking.objects.count()} created")

        # ── 6. Expenses ───────────────────────────────────────────
        # category values must be lowercase (matches model TextChoices)
        # payment_method is required
        exp_data = [
            ("construction",  "Al-Noor Contractors",   "Foundation work Phase 1"),
            ("marketing",     "Geo TV Ads",             "TV advertisement campaign"),
            ("salaries",      "Internal",               "Staff salaries March"),
            ("utilities",     "WAPDA",                  "Electricity bills Q1"),
            ("legal",         "Hassan & Associates",    "NOC documentation"),
            ("miscellaneous", "Various",                "Office supplies"),
            ("construction",  "Steel Mart",             "Steel procurement"),
            ("marketing",     "Facebook Ads",           "Social media campaign"),
            ("salaries",      "Internal",               "Staff salaries April"),
            ("construction",  "Pak Cement",             "Cement purchase batch 2"),
        ]
        payment_methods = ["cash", "transfer", "cheque"]

        for i, (category, vendor, description) in enumerate(exp_data):
            Expense.objects.get_or_create(
                vendor_name=vendor,
                description=description,
                defaults={
                    "project":          random.choice(projects),
                    "submitted_by":     staff_user,
                    "category":         category,
                    "amount":           Decimal(random.randint(50_000, 500_000)),
                    "date":             date.today() - timedelta(days=random.randint(10, 300)),
                    "payment_method":   random.choice(payment_methods),
                    "reference_number": f"REF-{1000 + i}",
                },
            )

        self.stdout.write(f"  Expenses: {Expense.objects.count()} created")
        self.stdout.write(self.style.SUCCESS("Seed data loaded successfully."))
        self.stdout.write("  Login: admin / admin123")