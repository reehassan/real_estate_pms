"""
Management command to seed the database with realistic test data.
Run: python manage.py seed_data
"""

import random
from datetime import date, timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.contrib.auth import get_user_model

from apps.projects_and_plots.models import Project, Plot
from apps.customers.models import Customer
from apps.bookings.models import Booking, Installment
# from apps.expenses.models import Expense

User = get_user_model()


class Command(BaseCommand):
    help = 'Seed the database with test data for development'

    def add_arguments(self, parser):
        parser.add_argument(
            '--projects',
            type=int,
            default=3,
            help='Number of projects to create (default: 3)'
        )
        parser.add_argument(
            '--plots-per-project',
            type=int,
            default=20,
            help='Number of plots per project (default: 20)'
        )
        parser.add_argument(
            '--customers',
            type=int,
            default=50,
            help='Number of customers to create (default: 50)'
        )
        parser.add_argument(
            '--bookings',
            type=int,
            default=30,
            help='Number of bookings to create (default: 30)'
        )

    def handle(self, *args, **options):
        self.stdout.write("Seeding database...")

        # Get or create admin user for 'booked_by'
        admin_user = User.objects.filter(is_superuser=True).first()
        if not admin_user:
            admin_user = User.objects.create_superuser(
                username='admin',
                email='admin@example.com',
                password='admin123'
            )
            self.stdout.write("Created superuser 'admin' with password 'admin123'")

        # 1. Create Projects
        projects = []
        project_codes = ['GHQ', 'GBS', 'PHA', 'DHA', 'BHC']
        project_names = [
            "Royal Land", "Green Bay Society", "Park View Housing",
            "Defence Housing", "Blue Heights City"
        ]
        locations = [
            "Lahore", "Karachi", "Islamabad", "Rawalpindi", "Multan"
        ]

        for i in range(options['projects']):
            code = project_codes[i] if i < len(project_codes) else f"PROJ{i+1:03d}"
            proj = Project.objects.create(
                name=project_names[i % len(project_names)],
                code=code,
                location=locations[i % len(locations)],
                total_plots=options['plots_per_project'],
                total_area=random.randint(500, 5000),
                status=random.choice(['ACTIVE', 'ACTIVE', 'ACTIVE', 'COMPLETED']),
                description=f"Test project {i+1} with {options['plots_per_project']} plots."
            )
            projects.append(proj)
        self.stdout.write(f"Created {len(projects)} projects")

        # 2. Create Plots for each project
        plot_statuses = ['AVAILABLE', 'AVAILABLE', 'BOOKED', 'SOLD']
        categories = ['RESIDENTIAL', 'COMMERCIAL']
        all_plots = []

        for proj in projects:
            for plot_num in range(1, options['plots_per_project'] + 1):
                status = random.choices(plot_statuses, weights=[0.5, 0.3, 0.15, 0.05])[0]
                plot = Plot.objects.create(
                    project=proj,
                    plot_number=f"{plot_num:03d}",
                    block=chr(65 + (plot_num % 26)),  # A, B, C...
                    size=random.choice([3, 5, 7, 10, 12.5]),
                    size_unit='MARLA',
                    category=random.choice(categories),
                    price=random.randint(500000, 5000000),
                    status=status,
                    notes=f"Test plot {plot_num}"
                )
                all_plots.append(plot)
        self.stdout.write(f"Created {len(all_plots)} plots")

        # 3. Create Customers
        customers = []
        first_names = ["Ali", "Sara", "Ahmed", "Fatima", "Bilal", "Zara", "Omar", "Hina", "Usman", "Ayesha"]
        last_names = ["Khan", "Malik", "Raza", "Chaudhry", "Tariq", "Hassan", "Butt", "Sheikh"]

        for i in range(options['customers']):
            full_name = f"{random.choice(first_names)} {random.choice(last_names)}"
            cnic = f"{random.randint(10000, 99999):05d}-{random.randint(1000000, 9999999):07d}-{random.randint(1, 9)}"
            phone = f"03{random.randint(0, 9):01d}{random.randint(10000000, 99999999):08d}"
            cust = Customer.objects.create(
                full_name=full_name,
                cnic=cnic,
                phone=phone,
                address=f"{random.randint(1, 200)} {random.choice(['Main Blvd', 'Street', 'Road'])}, {random.choice(locations)}",
                customer_type=random.choice(['INDIVIDUAL', 'JOINT', 'CORPORATE'])
            )
            customers.append(cust)
        self.stdout.write(f"Created {len(customers)} customers")

            # 4. Create Bookings (only on AVAILABLE plots)
        available_plots = list(Plot.objects.filter(status='AVAILABLE'))  # ← convert to list
        customers = list(customers)  # also convert to list for indexing

        # Shuffle lists
        random.shuffle(available_plots)
        random.shuffle(customers)

        bookings_created = 0
        payment_plans = ['lump', '3yr', '5yr']

        # Ensure we don't exceed available plots or customers
        max_bookings = min(options['bookings'], len(available_plots), len(customers))

        for i in range(max_bookings):
            plot = available_plots[i]
            customer = customers[i]
            plan = random.choice(payment_plans)
            total_price = plot.price
            down_payment = int(total_price * random.uniform(0.1, 0.3))
            booking_date = date.today() - timedelta(days=random.randint(0, 365))

            booking = Booking.objects.create(
                customer=customer,
                plot=plot,
                booking_date=booking_date,
                total_price=total_price,
                down_payment=down_payment,
                payment_plan=plan,
                status='ACTIVE',
                booked_by=admin_user,
                notes=f"Test booking {i+1}"
            )
            bookings_created += 1
            # Update plot status to BOOKED
            plot.status = 'BOOKED'
            plot.save()

        # # 5. Create some Expenses (approved and pending)
        # expense_categories = ['Marketing', 'Utilities', 'Salaries', 'Maintenance', 'Legal', 'Taxes']
        # expense_statuses = ['pending', 'approved', 'paid']

        # for _ in range(30):
        #     proj = random.choice(projects)
        #     amount = random.randint(5000, 200000)
        #     status = random.choice(expense_statuses)
        #     expense = Expense.objects.create(
        #         project=proj,
        #         category=random.choice(expense_categories),
        #         amount=amount,
        #         vendor_name=f"Vendor {random.randint(1,20)}",
        #         description=f"Expense for {proj.name}",
        #         date=date.today() - timedelta(days=random.randint(1, 90)),
        #         payment_method=random.choice(['Cash', 'Bank Transfer', 'Cheque']),
        #         status=status,
        #         submitted_by=admin_user,
        #         approved_by=admin_user if status == 'approved' else None,
        #     )
        self.stdout.write("Created 30 sample expenses")

        # 6. Randomly pay some installments (optional)
        installments = Installment.objects.filter(status='PENDING')
        for inst in installments[:random.randint(10, 30)]:
            inst.status = 'PAID'
            inst.amount_paid = inst.amount_due
            inst.paid_on = date.today() - timedelta(days=random.randint(1, 30))
            inst.save()
        self.stdout.write("Paid some installments randomly")

        self.stdout.write(self.style.SUCCESS("Database seeding completed!"))