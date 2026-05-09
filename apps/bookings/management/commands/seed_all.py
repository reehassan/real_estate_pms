"""
apps/bookings/management/commands/seed_all.py

Comprehensive Pakistani demo data for Royal Land PMS.
Covers the full flow: project → plot → customer → booking → installments → expenses

Run:
    python manage.py seed_all
    python manage.py seed_all --flush   # wipe first, then seed

Demo accounts:
    admin  / admin123   (superuser)
    staff1 / staff123   (senior sales)
    staff2 / staff123   (accounts)
"""

import random
from datetime import date, timedelta
from decimal import Decimal, ROUND_DOWN

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.accounts.models import User
from apps.bookings.models import Booking, Installment
from apps.bookings.services.installment_service import generate_installments
from apps.customers.models import Customer
from apps.expenses.models import Expense
from apps.projects_and_plots.models import Plot, Project


def d(value) -> Decimal:
    """Convert to Decimal safely."""
    return Decimal(str(value))


class Command(BaseCommand):
    help = "Load comprehensive Pakistani demo data"

    def add_arguments(self, parser):
        parser.add_argument(
            "--flush",
            action="store_true",
            help="Delete all existing data before seeding",
        )

    def handle(self, *args, **options):
        if options["flush"]:
            self.stdout.write(self.style.WARNING("Flushing existing data..."))
            Installment.all_objects.all().delete()
            Booking.all_objects.all().delete()
            Expense.all_objects.all().delete()
            Plot.all_objects.all().delete()
            Project.all_objects.all().delete()
            Customer.all_objects.all().delete()
            User.objects.filter(is_superuser=False).delete()
            self.stdout.write("  Flushed.")

        with transaction.atomic():
            self._seed_users()
            projects  = self._seed_projects()
            self._seed_plots(projects)
            customers = self._seed_customers()
            self._seed_bookings(customers)
            self._seed_expenses(projects)

        self.stdout.write(self.style.SUCCESS("\n✅  Seed complete!"))
        self.stdout.write("   admin  / admin123")
        self.stdout.write("   staff1 / staff123")
        self.stdout.write("   staff2 / staff123")

    # =========================================================================
    # 1. USERS
    # =========================================================================

    def _seed_users(self):
        self.admin, _ = User.objects.get_or_create(
            username="admin",
            defaults={
                "email":        "admin@royalland.pk",
                "first_name":   "Tariq",
                "last_name":    "Mehmood",
                "is_staff":     True,
                "is_superuser": True,
            },
        )
        self.admin.set_password("admin123")
        self.admin.save()

        self.staff1, _ = User.objects.get_or_create(
            username="staff1",
            defaults={
                "email":      "sales@royalland.pk",
                "first_name": "Kamran",
                "last_name":  "Hussain",
                "is_staff":   True,
            },
        )
        self.staff1.set_password("staff123")
        self.staff1.save()

        self.staff2, _ = User.objects.get_or_create(
            username="staff2",
            defaults={
                "email":      "accounts@royalland.pk",
                "first_name": "Sobia",
                "last_name":  "Nawaz",
                "is_staff":   True,
            },
        )
        self.staff2.set_password("staff123")
        self.staff2.save()

        self.stdout.write("  ✓ Users (3)")

    # =========================================================================
    # 2. PROJECTS
    # =========================================================================

    def _seed_projects(self):
        data = [
            {
                "name":        "Royal Land Residencia",
                "code":        "RLR",
                "location":    "Main GT Road, Rawalpindi, Punjab",
                "total_plots": 30,
                "total_area":  750,
                "area_unit":   "MARLA",
                "status":      "ACTIVE",
                "description": (
                    "Premium residential scheme on GT Road with underground electricity, "
                    "wide carpeted streets, mosque, and community park. NOC approved."
                ),
            },
            {
                "name":        "Green Oaks Islamabad",
                "code":        "GOI",
                "location":    "Sector B-17, MPCHS, Islamabad",
                "total_plots": 20,
                "total_area":  480,
                "area_unit":   "MARLA",
                "status":      "ACTIVE",
                "description": (
                    "Gated community in B-17 Islamabad. Walking distance from "
                    "Islamabad Motorway interchange. Ideal for families."
                ),
            },
            {
                "name":        "DHA Valley Commercial",
                "code":        "DVC",
                "location":    "DHA Phase 2 Extension, Lahore",
                "total_plots": 15,
                "total_area":  300,
                "area_unit":   "MARLA",
                "status":      "ACTIVE",
                "description": (
                    "Commercial plots in DHA Phase 2 Extension. "
                    "High footfall area, ideal for retail and office use."
                ),
            },
            {
                "name":        "Gulberg Heights Phase 2",
                "code":        "GHP",
                "location":    "Gulberg III, Lahore, Punjab",
                "total_plots": 12,
                "total_area":  240,
                "area_unit":   "MARLA",
                "status":      "PLANNING",
                "description": (
                    "Upcoming luxury residential project in Gulberg III. "
                    "Pre-launch bookings open. Possession in 24 months."
                ),
            },
            {
                "name":        "Bahria Orchard Extension",
                "code":        "BOE",
                "location":    "Bahria Orchard Phase 4, Lahore",
                "total_plots": 25,
                "total_area":  600,
                "area_unit":   "MARLA",
                "status":      "ACTIVE",
                "description": (
                    "Extension of the popular Bahria Orchard scheme. "
                    "5 Marla and 10 Marla plots with instalment plans up to 5 years."
                ),
            },
        ]

        projects = []
        for item in data:
            proj, _ = Project.objects.get_or_create(
                code=item["code"],
                defaults={k: v for k, v in item.items() if k != "code"},
            )
            projects.append(proj)

        self.stdout.write(f"  ✓ Projects ({len(projects)})")
        return projects

    # =========================================================================
    # 3. PLOTS
    # =========================================================================

    def _seed_plots(self, projects):
        # (project_code, block, plot_number, size, category, price, status)
        plot_specs = {
            "RLR": [
                # Block A — 5 Marla residential
                ("A", "101", "5",  "RESIDENTIAL", 3_500_000,  "AVAILABLE"),
                ("A", "102", "5",  "RESIDENTIAL", 3_500_000,  "AVAILABLE"),
                ("A", "103", "5",  "RESIDENTIAL", 3_500_000,  "TOKEN"),
                ("A", "104", "5",  "RESIDENTIAL", 3_500_000,  "BOOKED"),
                ("A", "105", "5",  "RESIDENTIAL", 3_500_000,  "BOOKED"),
                # Block B — 10 Marla residential
                ("B", "201", "10", "RESIDENTIAL", 7_000_000,  "AVAILABLE"),
                ("B", "202", "10", "RESIDENTIAL", 7_000_000,  "AVAILABLE"),
                ("B", "203", "10", "RESIDENTIAL", 7_000_000,  "BOOKED"),
                ("B", "204", "10", "RESIDENTIAL", 7_000_000,  "SOLD"),
                ("B", "205", "10", "RESIDENTIAL", 7_000_000,  "AVAILABLE"),
                # Block C — 1 Kanal residential
                ("C", "301", "20", "RESIDENTIAL", 14_000_000, "AVAILABLE"),
                ("C", "302", "20", "RESIDENTIAL", 14_000_000, "BOOKED"),
                ("C", "303", "20", "RESIDENTIAL", 14_000_000, "AVAILABLE"),
                # Block D — Commercial
                ("D", "401", "4",  "COMMERCIAL",  8_000_000,  "AVAILABLE"),
                ("D", "402", "4",  "COMMERCIAL",  8_000_000,  "BOOKED"),
                ("D", "403", "4",  "COMMERCIAL",  8_500_000,  "SOLD"),
                ("D", "404", "4",  "COMMERCIAL",  8_500_000,  "AVAILABLE"),
                ("D", "405", "5",  "COMMERCIAL",  10_000_000, "AVAILABLE"),
            ],
            "GOI": [
                ("A", "101", "5",  "RESIDENTIAL", 4_200_000,  "AVAILABLE"),
                ("A", "102", "5",  "RESIDENTIAL", 4_200_000,  "BOOKED"),
                ("A", "103", "5",  "RESIDENTIAL", 4_200_000,  "TOKEN"),
                ("A", "104", "5",  "RESIDENTIAL", 4_200_000,  "AVAILABLE"),
                ("B", "201", "10", "RESIDENTIAL", 8_500_000,  "AVAILABLE"),
                ("B", "202", "10", "RESIDENTIAL", 8_500_000,  "BOOKED"),
                ("B", "203", "10", "RESIDENTIAL", 8_500_000,  "SOLD"),
                ("B", "204", "10", "RESIDENTIAL", 8_500_000,  "AVAILABLE"),
                ("C", "301", "8",  "RESIDENTIAL", 6_800_000,  "BOOKED"),
                ("C", "302", "8",  "RESIDENTIAL", 6_800_000,  "AVAILABLE"),
            ],
            "DVC": [
                ("A", "101", "4",  "COMMERCIAL",  12_000_000, "AVAILABLE"),
                ("A", "102", "4",  "COMMERCIAL",  12_000_000, "BOOKED"),
                ("A", "103", "4",  "COMMERCIAL",  12_000_000, "AVAILABLE"),
                ("A", "104", "8",  "COMMERCIAL",  22_000_000, "BOOKED"),
                ("A", "105", "8",  "COMMERCIAL",  22_000_000, "SOLD"),
                ("B", "201", "4",  "COMMERCIAL",  13_000_000, "AVAILABLE"),
                ("B", "202", "4",  "COMMERCIAL",  13_000_000, "AVAILABLE"),
                ("B", "203", "8",  "COMMERCIAL",  24_000_000, "AVAILABLE"),
            ],
            "GHP": [
                ("A", "101", "5",  "RESIDENTIAL", 5_500_000,  "AVAILABLE"),
                ("A", "102", "5",  "RESIDENTIAL", 5_500_000,  "AVAILABLE"),
                ("A", "103", "10", "RESIDENTIAL", 11_000_000, "AVAILABLE"),
                ("A", "104", "10", "RESIDENTIAL", 11_000_000, "TOKEN"),
            ],
            "BOE": [
                ("A", "101", "5",  "RESIDENTIAL", 3_200_000,  "AVAILABLE"),
                ("A", "102", "5",  "RESIDENTIAL", 3_200_000,  "BOOKED"),
                ("A", "103", "5",  "RESIDENTIAL", 3_200_000,  "BOOKED"),
                ("A", "104", "5",  "RESIDENTIAL", 3_200_000,  "AVAILABLE"),
                ("A", "105", "5",  "RESIDENTIAL", 3_200_000,  "TOKEN"),
                ("B", "201", "10", "RESIDENTIAL", 6_500_000,  "AVAILABLE"),
                ("B", "202", "10", "RESIDENTIAL", 6_500_000,  "BOOKED"),
                ("B", "203", "10", "RESIDENTIAL", 6_500_000,  "SOLD"),
                ("B", "204", "10", "RESIDENTIAL", 6_500_000,  "AVAILABLE"),
                ("C", "301", "20", "RESIDENTIAL", 13_000_000, "BOOKED"),
                ("C", "302", "20", "RESIDENTIAL", 13_000_000, "AVAILABLE"),
            ],
        }

        proj_map = {p.code: p for p in projects}
        total = 0

        for code, specs in plot_specs.items():
            proj = proj_map[code]
            for block, plot_num, size, category, price, status in specs:
                Plot.objects.get_or_create(
                    project=proj,
                    plot_number=plot_num,
                    defaults={
                        "block":    block,
                        "size":     d(size),
                        "size_unit":"MARLA",
                        "category": category,
                        "price":    d(price),
                        "status":   status,
                    },
                )
                total += 1

        self.stdout.write(f"  ✓ Plots ({total})")

    # =========================================================================
    # 4. CUSTOMERS
    # =========================================================================

    def _seed_customers(self):
        data = [
            # (full_name, cnic, phone, address, type)
            ("Muhammad Tariq Butt",    "35202-1234567-1", "03001234567",
             "House 14, Street 5, Satellite Town, Rawalpindi", "INDIVIDUAL"),

            ("Asma Shahid",            "35202-2345678-2", "03012345678",
             "Flat 3B, Al-Hamra Heights, F-10/3, Islamabad", "INDIVIDUAL"),

            ("Khalid Mehmood",         "42301-3456789-3", "03023456789",
             "Plot 22, Block D, DHA Phase 5, Lahore", "INDIVIDUAL"),

            ("Rukhsana Perveen",       "35202-4567890-4", "03034567890",
             "House 7, Gulberg II, Lahore", "INDIVIDUAL"),

            ("Rana Zulfiqar Ali",      "61101-5678901-5", "03045678901",
             "House 45, Sector G-9/2, Islamabad", "INDIVIDUAL"),

            ("Nosheen Akhtar",         "35202-6789012-6", "03056789012",
             "House 3, Street 12, Model Town, Lahore", "INDIVIDUAL"),

            ("Arshad Karim & Sons",    "35202-7890123-7", "03067890123",
             "Office 12, 2nd Floor, Saddar, Rawalpindi", "CORPORATE"),

            ("Saima Riaz",             "42301-8901234-8", "03078901234",
             "House 8, Bahria Town Phase 4, Rawalpindi", "INDIVIDUAL"),

            ("Imtiaz Ahmed Sheikh",    "61101-9012345-9", "03089012345",
             "House 33, Johar Town, Lahore", "INDIVIDUAL"),

            ("Faisal & Kamran (Joint)","35202-0123456-0", "03090123456",
             "House 18, PWD Housing Society, Islamabad", "JOINT"),

            ("Dr. Ayesha Siddiqui",    "35201-1122334-5", "03111223344",
             "House 9, F-7/2, Islamabad", "INDIVIDUAL"),

            ("Chaudhry Pervaiz Iqbal", "35202-5544332-1", "03215544332",
             "House 100, Wapda Town, Lahore", "INDIVIDUAL"),

            ("Maryam Nawaz Enterprises","42201-9988776-3", "03219988776",
             "Plot 5, Korangi Industrial Area, Karachi", "CORPORATE"),

            ("Adnan Malik",            "35202-3322114-7", "03333322114",
             "House 55, Street 3, G-11/1, Islamabad", "INDIVIDUAL"),

            ("Hina Javed",             "61101-6677889-2", "03446677889",
             "House 72, Askari 10, Lahore Cantt", "INDIVIDUAL"),
        ]

        customers = []
        for full_name, cnic, phone, address, ctype in data:
            cust, _ = Customer.objects.get_or_create(
                cnic=cnic,
                defaults={
                    "full_name":     full_name,
                    "phone":         phone,
                    "address":       address,
                    "customer_type": ctype,
                },
            )
            customers.append(cust)

        self.stdout.write(f"  ✓ Customers ({len(customers)})")
        return customers

    # =========================================================================
    # 5. BOOKINGS + INSTALLMENTS
    # =========================================================================

    def _seed_bookings(self, customers):
        """
        Create realistic bookings covering every status:
        - TOKEN  : 2 bookings (just token paid, DP pending)
        - ACTIVE : multiple bookings with full installment schedules
        - COMPLETED : 1 booking with all installments paid
        - CANCELLED : 1 soft-deleted booking (shows audit trail)

        Also marks some installments as OVERDUE and some as PAID
        to give a realistic mid-project picture.
        """

        staff_choices = [self.staff1, self.staff2]

        # ── Helper ────────────────────────────────────────────────
        def make_booking(plot_code, plot_num, customer, plan,
                         booking_days_ago, token_pct, dp_pct,
                         status=Booking.Status.ACTIVE,
                         block="A"):
            try:
                plot = Plot.objects.get(
                    project__code=plot_code,
                    plot_number=plot_num,
                )
            except Plot.DoesNotExist:
                return None

            if Booking.objects.filter(
                plot=plot,
                status__in=[Booking.Status.ACTIVE, Booking.Status.TOKEN],
                is_deleted=False,
            ).exists():
                return None

            total_price  = plot.price
            token_amount = (total_price * d(token_pct)).quantize(d("0.01"))
            down_payment = (total_price * d(dp_pct)).quantize(d("0.01"))
            booking_date = date.today() - timedelta(days=booking_days_ago)
            token_date   = booking_date
            dp_date      = booking_date + timedelta(days=14)

            booking = Booking.objects.create(
                customer                 = customer,
                plot                     = plot,
                booked_by                = random.choice(staff_choices),
                booking_date             = booking_date,
                total_price              = total_price,
                token_amount             = token_amount,
                token_received_on        = token_date,
                down_payment             = down_payment,
                down_payment_received_on = dp_date if status == Booking.Status.ACTIVE else None,
                payment_plan             = plan,
                status                   = status,
                notes                    = f"Booking processed by {random.choice(staff_choices).get_full_name()}.",
            )

            if status == Booking.Status.ACTIVE:
                generate_installments(booking)

            return booking

        # ── TOKEN bookings (2) ────────────────────────────────────
        make_booking("RLR", "103", customers[2],  Booking.PaymentPlan.ONE_YEAR,
                     10, "0.05", "0.15", Booking.Status.TOKEN)

        make_booking("GOI", "103", customers[13], Booking.PaymentPlan.TWO_YEAR,
                     5,  "0.05", "0.20", Booking.Status.TOKEN)

        make_booking("BOE", "105", customers[10], Booking.PaymentPlan.THREE_YEAR,
                     3,  "0.05", "0.15", Booking.Status.TOKEN)

        # ── ACTIVE bookings — various plans ───────────────────────
        active_specs = [
            # (project, plot, customer_idx, plan, days_ago, token%, dp%)
            ("RLR", "104", 0,  Booking.PaymentPlan.ONE_YEAR,   180, "0.05", "0.20"),
            ("RLR", "105", 1,  Booking.PaymentPlan.TWO_YEAR,   150, "0.05", "0.15"),
            ("RLR", "203", 3,  Booking.PaymentPlan.THREE_YEAR, 120, "0.10", "0.20"),
            ("RLR", "302", 4,  Booking.PaymentPlan.FIVE_YEAR,  200, "0.05", "0.15"),
            ("RLR", "402", 6,  Booking.PaymentPlan.ONE_YEAR,   90,  "0.10", "0.25"),
            ("RLR", "405", 9,  Booking.PaymentPlan.TWO_YEAR,   60,  "0.05", "0.20"),
            ("GOI", "102", 5,  Booking.PaymentPlan.THREE_YEAR, 240, "0.05", "0.15"),
            ("GOI", "202", 7,  Booking.PaymentPlan.FIVE_YEAR,  300, "0.05", "0.10"),
            ("GOI", "301", 11, Booking.PaymentPlan.TWO_YEAR,   160, "0.10", "0.20"),
            ("DVC", "102", 8,  Booking.PaymentPlan.THREE_YEAR, 180, "0.10", "0.20"),
            ("DVC", "104", 12, Booking.PaymentPlan.FIVE_YEAR,  365, "0.05", "0.15"),
            ("BOE", "102", 2,  Booking.PaymentPlan.ONE_YEAR,   90,  "0.05", "0.20"),
            ("BOE", "103", 14, Booking.PaymentPlan.TWO_YEAR,   120, "0.05", "0.15"),
            ("BOE", "202", 10, Booking.PaymentPlan.THREE_YEAR, 270, "0.10", "0.20"),
            ("BOE", "301", 13, Booking.PaymentPlan.FIVE_YEAR,  400, "0.05", "0.10"),
        ]

        active_bookings = []
        for proj, plot_num, cidx, plan, days, tok, dp in active_specs:
            b = make_booking(proj, plot_num, customers[cidx], plan,
                             days, tok, dp, Booking.Status.ACTIVE)
            if b:
                active_bookings.append(b)

        # ── COMPLETED booking — all installments paid ─────────────
        completed = make_booking(
            "RLR", "204", customers[1],
            Booking.PaymentPlan.ONE_YEAR,
            400, "0.10", "0.20",
            Booking.Status.ACTIVE,
        )
        if completed:
            completed.status = Booking.Status.COMPLETED
            completed.save(update_fields=["status", "updated_at"])
            today = date.today()
            for i, inst in enumerate(completed.installments.order_by("installment_number")):
                inst.amount_paid = inst.amount_due
                inst.paid_on     = today - timedelta(days=350 - (i * 28))
                inst.status      = Installment.Status.PAID
                inst.save(update_fields=["amount_paid", "paid_on", "status"])

        # ── CANCELLED booking — shows audit trail ─────────────────
        cancelled = make_booking(
            "RLR", "403", customers[8],
            Booking.PaymentPlan.ONE_YEAR,
            45, "0.05", "0.15",
            Booking.Status.ACTIVE,
        )
        if cancelled:
            cancelled.delete()  # soft delete → CANCELLED + plot → AVAILABLE

        # ── Mark some installments PAID (partial progress) ────────
        for booking in active_bookings[:6]:
            insts = list(
                booking.installments
                .filter(status=Installment.Status.PENDING)
                .order_by("installment_number")
            )
            paid_count = random.randint(1, max(1, len(insts) // 3))
            for i, inst in enumerate(insts[:paid_count]):
                inst.amount_paid = inst.amount_due
                inst.paid_on     = inst.due_date + timedelta(days=random.randint(0, 7))
                inst.status      = Installment.Status.PAID
                inst.save(update_fields=["amount_paid", "paid_on", "status"])

        # ── Mark overdue installments ─────────────────────────────
        overdue = Installment.objects.filter(
            status=Installment.Status.PENDING,
            due_date__lt=date.today() - timedelta(days=15),
        )[:8]
        for inst in overdue:
            inst.status = Installment.Status.OVERDUE
            inst.save(update_fields=["status"])

        total_bookings     = Booking.all_objects.count()
        total_installments = Installment.objects.count()
        self.stdout.write(f"  ✓ Bookings ({total_bookings}) — Installments ({total_installments})")

    # =========================================================================
    # 6. EXPENSES
    # =========================================================================

    def _seed_expenses(self, projects):
        proj_map = {p.code: p for p in projects}

        data = [
            # RLR — Active large project
            ("RLR", "construction", "Al-Noor Contractors",
             "Boundary wall construction Phase 1",
             1_800_000, "cheque",   "PO-2024-001", 280),

            ("RLR", "construction", "Pak Steel Traders",
             "Steel rebar procurement 50 tons",
             2_200_000, "transfer", "PO-2024-002", 260),

            ("RLR", "construction", "Lahore Cement Depot",
             "Cement purchase 500 bags batch 1",
             650_000,   "cash",     "PO-2024-003", 240),

            ("RLR", "construction", "Lahore Cement Depot",
             "Cement purchase 500 bags batch 2",
             680_000,   "cash",     "PO-2024-018", 90),

            ("RLR", "marketing", "Geo TV",
             "30-second TVC for Royal Land Residencia",
             950_000,   "cheque",   "MKT-001", 200),

            ("RLR", "marketing", "Jang Group Newspapers",
             "Full-page ad in Jang — launch announcement",
             180_000,   "cheque",   "MKT-002", 195),

            ("RLR", "marketing", "Digital Boost Agency",
             "Facebook & Instagram campaign — Q1 2025",
             120_000,   "transfer", "MKT-003", 100),

            ("RLR", "marketing", "OOH Media Pakistan",
             "Billboard rental GT Road — 3 months",
             240_000,   "cheque",   "MKT-004", 60),

            ("RLR", "legal", "Hassan & Associates",
             "NOC application and documentation fee",
             350_000,   "cheque",   "LEG-001", 350),

            ("RLR", "legal", "Hassan & Associates",
             "LDA approval processing",
             180_000,   "cheque",   "LEG-002", 300),

            ("RLR", "salaries", "Internal Payroll",
             "Staff salaries — January 2025",
             420_000,   "transfer", "SAL-JAN-25", 120),

            ("RLR", "salaries", "Internal Payroll",
             "Staff salaries — February 2025",
             420_000,   "transfer", "SAL-FEB-25", 90),

            ("RLR", "salaries", "Internal Payroll",
             "Staff salaries — March 2025",
             420_000,   "transfer", "SAL-MAR-25", 60),

            ("RLR", "salaries", "Internal Payroll",
             "Staff salaries — April 2025",
             420_000,   "transfer", "SAL-APR-25", 30),

            ("RLR", "utilities", "WAPDA Rawalpindi",
             "Electricity bill — construction site Q1",
             85_000,    "cash",     "UTIL-001", 100),

            ("RLR", "utilities", "PTCL",
             "Internet and telephone — office Rawalpindi",
             18_000,    "cash",     "UTIL-002", 70),

            ("RLR", "miscellaneous", "Office Zone",
             "Stationery and printing supplies",
             25_000,    "cash",     "MISC-001", 50),

            ("RLR", "miscellaneous", "Toyota Rawalpindi",
             "Vehicle fuel and maintenance — Q1",
             65_000,    "cash",     "MISC-002", 40),

            # GOI — Islamabad project
            ("GOI", "construction", "Capital Builders",
             "Site development and leveling",
             3_200_000, "cheque",   "GOI-CON-001", 320),

            ("GOI", "construction", "Islamabad Tiles",
             "Boundary wall tiling and finishing",
             450_000,   "transfer", "GOI-CON-002", 180),

            ("GOI", "marketing", "ARY News",
             "Property show sponsorship — Green Oaks",
             750_000,   "cheque",   "GOI-MKT-001", 150),

            ("GOI", "legal", "Malik Law Associates",
             "CDA NOC and site approval",
             280_000,   "cheque",   "GOI-LEG-001", 400),

            ("GOI", "salaries", "Internal Payroll",
             "Islamabad office salaries Q1 2025",
             380_000,   "transfer", "GOI-SAL-Q1", 90),

            ("GOI", "utilities", "IESCO",
             "Electricity — Islamabad office and site",
             62_000,    "cash",     "GOI-UTIL-001", 75),

            # DVC — Commercial Lahore
            ("DVC", "construction", "DHA Approved Contractors",
             "Infrastructure development Phase 1",
             4_500_000, "cheque",   "DVC-CON-001", 250),

            ("DVC", "marketing", "Express Tribune",
             "Commercial plots advertisement",
             220_000,   "cheque",   "DVC-MKT-001", 120),

            ("DVC", "legal", "Chaudhry & Partners",
             "DHA approval and NOC processing",
             500_000,   "cheque",   "DVC-LEG-001", 300),

            # BOE — Bahria Orchard
            ("BOE", "construction", "Bahria Approved Vendor",
             "Road construction and carpeting",
             2_800_000, "cheque",   "BOE-CON-001", 310),

            ("BOE", "construction", "Green Park Landscaping",
             "Park and green area development",
             680_000,   "transfer", "BOE-CON-002", 200),

            ("BOE", "marketing", "Samaa TV",
             "TVC campaign for Bahria Orchard Extension",
             850_000,   "cheque",   "BOE-MKT-001", 160),

            ("BOE", "salaries", "Internal Payroll",
             "Lahore office salaries Q1 2025",
             390_000,   "transfer", "BOE-SAL-Q1", 85),

            ("BOE", "miscellaneous", "Al-Fatah Stores",
             "Office furniture — Lahore branch",
             145_000,   "cash",     "BOE-MISC-001", 95),
        ]

        count = 0
        for code, category, vendor, description, amount, method, ref, days_ago in data:
            proj = proj_map.get(code)
            if not proj:
                continue
            Expense.objects.get_or_create(
                reference_number=ref,
                defaults={
                    "project":        proj,
                    "submitted_by":   self.staff2,
                    "category":       category,
                    "amount":         d(amount),
                    "vendor_name":    vendor,
                    "description":    description,
                    "date":           date.today() - timedelta(days=days_ago),
                    "payment_method": method,
                },
            )
            count += 1

        self.stdout.write(f"  ✓ Expenses ({count})")