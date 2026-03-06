from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db import transaction
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend, FilterSet, DateFromToRangeFilter
import weasyprint
from .models import Invoice, InvoiceHistory
from .serializers import InvoiceSerializer, InvoiceFromQuoteSerializer
from clients.models import Address
from rest_framework.permissions import IsAuthenticated


# Filters
class InvoiceFilter(FilterSet):
    date_emission = DateFromToRangeFilter()
    date_echeance = DateFromToRangeFilter()

    class Meta:
        model = Invoice
        fields = {
            'client': ['exact'],
            'statut': ['exact'],
            'devis_origine': ['exact', 'isnull'],
        }


# ViewSet
class InvoiceViewSet(viewsets.ModelViewSet):
    """
    CRUD for invoices with nested lines.

    list:            GET    /invoices/
    create:          POST   /invoices/
    retrieve:        GET    /invoices/{id}/
    update:          PUT    /invoices/{id}/
    partial_update:  PATCH  /invoices/{id}/
    destroy:         DELETE /invoices/{id}/
    changer_statut:  POST   /invoices/{id}/changer-statut/
    from_devis:      POST   /invoices/from-devis/
    """

    serializer_class = InvoiceSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = InvoiceFilter
    search_fields = ['numero', 'objet']
    ordering_fields = ['date_emission', 'date_echeance', 'created_at', 'total_ttc']
    ordering = ['-date_emission', '-created_at']

    def get_queryset(self):
        return (
            Invoice.objects
            .filter(utilisateur=self.request.user)
            .prefetch_related('lignes', 'historique')
        )

    def perform_create(self, serializer):
        serializer.save(utilisateur=self.request.user)

    def perform_destroy(self, instance):
        """Soft delete — only if DRAFT"""
        if not instance.is_deletable:
            raise PermissionError("Only a draft invoice can be deleted.")
        instance.delete()

    def destroy(self, request, *args, **kwargs):
        try:
            return super().destroy(request, *args, **kwargs)
        except PermissionError as e:
            return Response(
                {'detail': str(e)},
                status=status.HTTP_403_FORBIDDEN,
            )

    # Action: status change
    TRANSITIONS = {
        Invoice.STATUT_BROUILLON: [Invoice.STATUT_ENVOYEE],
        Invoice.STATUT_ENVOYEE: [Invoice.STATUT_PAYEE, Invoice.STATUT_EN_RETARD],
        Invoice.STATUT_EN_RETARD: [Invoice.STATUT_PAYEE],
        Invoice.STATUT_PAYEE: [],
    }

    @action(detail=True, methods=['post'])
    def changer_statut(self, request, pk=None):
        """
        POST /invoices/{id}/changer_statut/
        Body: { "statut": "ENVOYEE" }
        """
        invoice = self.get_object()
        new_status = request.data.get('statut')

        if not new_status:
            return Response(
                {'statut': "This field is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        allowed_transitions = self.TRANSITIONS.get(invoice.statut, [])
        if new_status not in allowed_transitions:
            return Response(
                {
                    'statut': (
                        f"Transition from '{invoice.statut}' to '{new_status}' "
                        f"is not allowed. Allowed transitions: {allowed_transitions}"
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            old_status = invoice.statut
            invoice.statut = new_status

            # Generate number when transitioning to SENT
            if new_status == Invoice.STATUT_ENVOYEE and not invoice.numero:
                invoice.numero = self._generate_number(invoice.utilisateur)

            invoice.save(update_fields=['statut', 'numero'])

            InvoiceHistory.objects.create(
                facture=invoice,
                ancien_statut=old_status,
                nouveau_statut=new_status,
            )

        serializer = self.get_serializer(invoice)
        return Response(serializer.data)

    @staticmethod
    def _generate_number(user):
        """
        Generate invoice number from UserConfiguration.
        Format: PREFIX-YEAR-NUMBER (e.g. FAC-2025-001)
        """
        from accounts.models import UserConfiguration

        config = UserConfiguration.objects.select_for_update().get(user=user)
        year = timezone.now().year
        number = f"{config.invoice_prefix}-{year}-{config.next_invoice_number:03d}"
        config.next_invoice_number += 1
        config.save(update_fields=['next_invoice_number'])
        return number


    # Action: create invoice from quote
    @action(detail=False, methods=['post'], url_path='from-devis')
    def from_devis(self, request):
        """
        POST /invoices/from-devis/
        Body: { "devis_id": 1 }
        """
        serializer = InvoiceFromQuoteSerializer(
            data=request.data,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        invoice = serializer.save()

        return Response(
            InvoiceSerializer(invoice).data,
            status=status.HTTP_201_CREATED,
        )


    # Action: generate PDF
    @action(detail=True, methods=['get'], url_path='pdf')
    def generate_pdf(self, request, pk=None):
        """
        GET /invoices/{id}/pdf/
        Generate and return the invoice PDF.
        """
        invoice = self.get_object()
        lines = invoice.lignes.all()

        # Client billing address (fallback to headquarters)
        address = (
            Address.objects
            .filter(client=invoice.client, type=Address.AddressType.FACTURATION)
            .first()
        ) or (
            Address.objects
            .filter(client=invoice.client, type=Address.AddressType.SIEGE)
            .first()
        )

        html = render_to_string('invoices/facture_pdf.html', {
            'facture': invoice,
            'lignes': lines,
            'adresse': address,
            'utilisateur': invoice.utilisateur,
        })

        pdf = weasyprint.HTML(string=html).write_pdf()

        filename = f"{invoice.numero or f'draft-{invoice.pk}'}.pdf"
        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
