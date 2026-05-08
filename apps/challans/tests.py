"""
apps/challans/tests.py

Tests for the challan PDF view.

Coverage:
    test_challan_requires_login           — unauthenticated → 302 to login
    test_challan_returns_pdf              — authenticated → 200 + application/pdf
    test_challan_content_disposition      — filename matches challan_number
    test_challan_404_for_missing_id       — nonexistent installment → 404
    test_challan_404_for_soft_deleted     — soft-deleted installment → 404
    test_challan_staff_can_access         — is_staff user can download
    test_challan_superuser_can_access     — superuser can download

WeasyPrint is mocked — tests verify view logic, not PDF rendering.
"""

from datetime import date
from decimal import Decimal
from unittest.mock import patch, MagicMock

from django.contrib.auth import get_user_model
from django.test import TestCase, Client
from django.urls import reverse

from apps.bookings.models import Booking, Installment
from apps.customers.models import Customer
from apps.projects_and_plots.models import Plot, Project

User = get_user_model()


# ─────────────────────────────────────────────
# FACTORY
# ─────────────────────────────────────────────

class _F:
    @staticmethod
    def project():
        return Project.objects.create(
            name       = 'Test Project',
            code       = 'TST',
            location   = 'Islamabad',
            total_area = 100,
            status     = Project.Status.ACTIVE,
        )

    @staticmethod
    def plot(project):
        return Plot.objects.create(
            project    = project,
            plot_number= 'A-01',
            size       = Decimal('5.00'),
            size_unit  = Plot.SizeUnit.MARLA,
            category   = Plot.Category.RESIDENTIAL,
            price      = Decimal('1000000'),
            status     = Plot.Status.AVAILABLE,
        )

    @staticmethod
    def customer():
        return Customer.objects.create(
            full_name     = 'Test Customer',
            cnic          = '35001-1234567-1',
            phone         = '03001234567',
            address       = 'Rawalpindi',
            customer_type = Customer.CustomerType.INDIVIDUAL,
        )

    @staticmethod
    def user(is_staff=True, is_superuser=False):
        n = User.objects.count() + 1
        return User.objects.create_user(
            username     = f'staff{n}',
            email        = f'staff{n}@test.com',
            password     = 'testpass123',
            is_staff     = is_staff,
            is_superuser = is_superuser,
        )

    @classmethod
    def booking(cls, plot, customer):
        return Booking.objects.create(
            customer     = customer,
            plot         = plot,
            payment_plan = Booking.PaymentPlan.ONE_YEAR,
            status       = Booking.Status.ACTIVE,
            total_price  = Decimal('1000000'),
            token_amount = Decimal('50000'),
            down_payment = Decimal('150000'),
            booking_date = date(2024, 1, 1),
        )

    @classmethod
    def installment(cls, booking):
        """Signal already generated installments on ACTIVE booking — just return the first."""
        return booking.installments.order_by('installment_number').first()


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def _pdf_url(installment_id):
    return reverse('challans:pdf', args=[installment_id])


FAKE_PDF = b'%PDF-1.4 fake pdf bytes'


# ─────────────────────────────────────────────
# TESTS
# ─────────────────────────────────────────────

class ChallanViewTests(TestCase):

    def setUp(self):
        self.client   = Client()
        self.project  = _F.project()
        self.plot     = _F.plot(self.project)
        self.customer = _F.customer()
        self.booking  = _F.booking(self.plot, self.customer)
        # Signal generated 12 installments — grab the first one
        self.inst     = _F.installment(self.booking)
        # Guard: if signal didn't fire for some reason, fail fast
        self.assertIsNotNone(self.inst, "No installments generated — check signal wiring")
        self.url      = _pdf_url(self.inst.pk)
    # ── Auth ──────────────────────────────────────────────────────

    def test_challan_requires_login(self):
        """Unauthenticated request must redirect to login page."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response['Location'])

    def test_challan_requires_login_next_param_set(self):
        """After login the user should be redirected back to the challan URL."""
        response = self.client.get(self.url)
        self.assertIn('next=', response['Location'])

    # ── Successful response ───────────────────────────────────────

    @patch('apps.challans.views.HTML')
    def test_challan_returns_200_for_staff(self, mock_html):
        mock_html.return_value.write_pdf.return_value = FAKE_PDF
        user = _F.user(is_staff=True)
        self.client.login(username=user.username, password='testpass123')

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)

    @patch('apps.challans.views.HTML')
    def test_challan_content_type_is_pdf(self, mock_html):
        mock_html.return_value.write_pdf.return_value = FAKE_PDF
        user = _F.user(is_staff=True)
        self.client.login(username=user.username, password='testpass123')

        response = self.client.get(self.url)

        self.assertEqual(response['Content-Type'], 'application/pdf')

    @patch('apps.challans.views.HTML')
    def test_challan_content_disposition_uses_challan_number(self, mock_html):
        """Filename in Content-Disposition must match the installment's challan_number."""
        mock_html.return_value.write_pdf.return_value = FAKE_PDF
        user = _F.user(is_staff=True)
        self.client.login(username=user.username, password='testpass123')

        response = self.client.get(self.url)

        expected = f'attachment; filename="{self.inst.challan_number}.pdf"'
        self.assertEqual(response['Content-Disposition'], expected)

    @patch('apps.challans.views.HTML')
    def test_challan_response_body_is_pdf_bytes(self, mock_html):
        mock_html.return_value.write_pdf.return_value = FAKE_PDF
        user = _F.user(is_staff=True)
        self.client.login(username=user.username, password='testpass123')

        response = self.client.get(self.url)

        self.assertEqual(response.content, FAKE_PDF)

    @patch('apps.challans.views.HTML')
    def test_superuser_can_access_challan(self, mock_html):
        mock_html.return_value.write_pdf.return_value = FAKE_PDF
        user = _F.user(is_staff=True, is_superuser=True)
        self.client.login(username=user.username, password='testpass123')

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)

    # ── 404 cases ─────────────────────────────────────────────────

    def test_challan_404_for_nonexistent_installment(self):
        user = _F.user(is_staff=True)
        self.client.login(username=user.username, password='testpass123')

        response = self.client.get(_pdf_url(99999))

        self.assertEqual(response.status_code, 404)

    def test_challan_404_for_soft_deleted_installment(self):
        """
        Soft-deleted installments are excluded by the default manager.
        The view uses Installment.objects — so deleted ones return 404.
        """
        self.inst.delete()
        user = _F.user(is_staff=True)
        self.client.login(username=user.username, password='testpass123')

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 404)

    # ── Context correctness ───────────────────────────────────────

    @patch('apps.challans.views.HTML')
    @patch('apps.challans.views.render_to_string')
    def test_challan_passes_correct_context(self, mock_render, mock_html):
        """
        Verify the view passes installment, booking, customer, plot,
        project, and total_installments to the template.
        """
        mock_render.return_value = '<html>fake</html>'
        mock_html.return_value.write_pdf.return_value = FAKE_PDF

        user = _F.user(is_staff=True)
        self.client.login(username=user.username, password='testpass123')
        self.client.get(self.url)

        # render_to_string was called once
        self.assertTrue(mock_render.called)
        _, context = mock_render.call_args[0][0], mock_render.call_args[0][1]

        self.assertEqual(context['installment'], self.inst)
        self.assertEqual(context['booking'],     self.booking)
        self.assertEqual(context['customer'],    self.customer)
        self.assertEqual(context['plot'],        self.plot)
        self.assertEqual(context['project'],     self.project)
        self.assertIn('total_installments',      context)

    @patch('apps.challans.views.HTML')
    @patch('apps.challans.views.render_to_string')
    def test_total_installments_count_is_correct(self, mock_render, mock_html):
        """total_installments should equal the number of installments on the booking."""
        mock_render.return_value = '<html>fake</html>'
        mock_html.return_value.write_pdf.return_value = FAKE_PDF

        # ONE_YEAR plan generates 12 installments via signal
        expected_count = self.booking.installments.count()
        self.assertEqual(expected_count, 12)

        user = _F.user(is_staff=True)
        self.client.login(username=user.username, password='testpass123')
        self.client.get(self.url)

        _, context = mock_render.call_args[0][0], mock_render.call_args[0][1]
        self.assertEqual(context['total_installments'], expected_count)