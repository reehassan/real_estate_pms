# apps/bookings/views.py
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.shortcuts import get_object_or_404
from django.utils import timezone
from weasyprint import HTML

from .models import Installment


def installment_receipt(request, installment_id):
    # Retrieve the installment
    installment = get_object_or_404(Installment, pk=installment_id)

    # Build context for the template
    booking = installment.booking
    context = {
        "challan_number": installment.challan_number,
        "customer_name": booking.customer.full_name,
        "project_name": booking.plot.project.name,
        "plot_number": booking.plot.plot_number,
        "booking_id": booking.id,
        "installment_number": installment.installment_number,
        "total_installments": booking.installments.count(),
        "amount_due": installment.amount_due,
        "amount_paid": installment.amount_paid,
        "paid_on": installment.paid_on or timezone.localdate(),
        "balance": installment.amount_due - installment.amount_paid,
        "request_date": timezone.localdate(),
    }

    # Render HTML to PDF
    html_string = render_to_string("admin/bookings/receipt.html", context, request=request)
    pdf_file = HTML(string=html_string).write_pdf()

    # Return PDF as a downloadable response
    response = HttpResponse(pdf_file, content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="receipt-{installment.challan_number}.pdf"'
    return response