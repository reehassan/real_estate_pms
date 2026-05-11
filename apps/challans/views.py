"""
apps/challans/views.py

Challan PDF generation view.
GET /challan/<installment_id>/pdf/
→ renders challan.html → WeasyPrint → returns PDF

Staff login required. No email. Download only.
"""

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string

from apps.bookings.models import Installment


@login_required
def challan_pdf(request, installment_id):
    from weasyprint import HTML
    installment = get_object_or_404(
        Installment.objects
        .select_related(
            'booking__customer',
            'booking__plot__project',
            'booking__booked_by',
        ),
        pk=installment_id,
    )

    booking  = installment.booking
    customer = booking.customer
    plot     = booking.plot
    project  = plot.project

    total_installments = booking.installments.count()

    context = {
        'installment':       installment,
        'booking':           booking,
        'customer':          customer,
        'plot':              plot,
        'project':           project,
        'total_installments': total_installments,
    }

    html_string = render_to_string('challans/challan.html', context, request=request)
    pdf         = HTML(string=html_string, base_url=request.build_absolute_uri('/')).write_pdf()

    filename = f'{installment.challan_number}.pdf'

    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response