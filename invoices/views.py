from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db import transaction
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend, FilterSet, DateFromToRangeFilter
import weasyprint
from .models import Facture, HistoriqueFacture
from .serializers import FactureSerializer, FactureFromDevisSerializer
from clients.models import Adresse
from rest_framework.permissions import IsAuthenticated


# -------------------------------------------------------------------------
# Filtres
# -------------------------------------------------------------------------

class FactureFilter(FilterSet):
    date_emission = DateFromToRangeFilter()
    date_echeance = DateFromToRangeFilter()

    class Meta:
        model = Facture
        fields = {
            'client': ['exact'],
            'statut': ['exact'],
            'devis_origine': ['exact', 'isnull'],
        }


# -------------------------------------------------------------------------
# ViewSet
# -------------------------------------------------------------------------

class FactureViewSet(viewsets.ModelViewSet):
    """
    CRUD sur les factures avec lignes imbriquées.

    list:            GET    /invoices/
    create:          POST   /invoices/
    retrieve:        GET    /invoices/{id}/
    update:          PUT    /invoices/{id}/
    partial_update:  PATCH  /invoices/{id}/
    destroy:         DELETE /invoices/{id}/
    changer_statut:  POST   /invoices/{id}/changer-statut/
    from_devis:      POST   /invoices/from-devis/
    """

    serializer_class = FactureSerializer
    permission_classes = [IsAuthenticated] 
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = FactureFilter
    search_fields = ['numero', 'objet']
    ordering_fields = ['date_emission', 'date_echeance', 'created_at', 'total_ttc']
    ordering = ['-date_emission', '-created_at']

    def get_queryset(self):
        return (
            Facture.objects
            .filter(utilisateur=self.request.user)
            .prefetch_related('lignes', 'historique')
        )

    def perform_create(self, serializer):
        serializer.save(utilisateur=self.request.user)

    def perform_destroy(self, instance):
        """Soft delete — uniquement si BROUILLON"""
        if not instance.est_supprimable:
            raise PermissionError("Seule une facture en brouillon peut être supprimée.")
        instance.delete()

    def destroy(self, request, *args, **kwargs):
        try:
            return super().destroy(request, *args, **kwargs)
        except PermissionError as e:
            return Response(
                {'detail': str(e)},
                status=status.HTTP_403_FORBIDDEN,
            )

    # -------------------------------------------------------------------------
    # Action : changement de statut
    # -------------------------------------------------------------------------

    TRANSITIONS = {
        Facture.STATUT_BROUILLON: [Facture.STATUT_ENVOYEE],
        Facture.STATUT_ENVOYEE: [Facture.STATUT_PAYEE, Facture.STATUT_EN_RETARD],
        Facture.STATUT_EN_RETARD: [Facture.STATUT_PAYEE],
        Facture.STATUT_PAYEE: [],
    }

    @action(detail=True, methods=['post'])
    def changer_statut(self, request, pk=None):
        """
        POST /invoices/{id}/changer_statut/
        Body : { "statut": "ENVOYEE" }
        """
        facture = self.get_object()
        nouveau_statut = request.data.get('statut')

        if not nouveau_statut:
            return Response(
                {'statut': "Ce champ est requis."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        transitions_possibles = self.TRANSITIONS.get(facture.statut, [])
        if nouveau_statut not in transitions_possibles:
            return Response(
                {
                    'statut': (
                        f"Transition de « {facture.statut} » vers « {nouveau_statut} » "
                        f"non autorisée. Transitions possibles : {transitions_possibles}"
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            ancien_statut = facture.statut
            facture.statut = nouveau_statut

            # Génération du numéro lors du passage à ENVOYEE
            if nouveau_statut == Facture.STATUT_ENVOYEE and not facture.numero:
                facture.numero = self._generer_numero(facture.utilisateur)

            facture.save(update_fields=['statut', 'numero'])

            HistoriqueFacture.objects.create(
                facture=facture,
                ancien_statut=ancien_statut,
                nouveau_statut=nouveau_statut,
            )

        serializer = self.get_serializer(facture)
        return Response(serializer.data)

    @staticmethod
    def _generer_numero(utilisateur):
        """
        Génère le numéro de facture à partir de la UserConfiguration.
        Format : PREFIXE-ANNEE-NUMERO (ex: FAC-2025-001)
        """
        from accounts.models import UserConfiguration

        config = UserConfiguration.objects.select_for_update().get(user=utilisateur)
        annee = timezone.now().year
        numero = f"{config.invoice_prefix}-{annee}-{config.next_invoice_number:03d}"
        config.next_invoice_number += 1
        config.save(update_fields=['next_invoice_number'])
        return numero

    # -------------------------------------------------------------------------
    # Action : créer une facture depuis un devis
    # -------------------------------------------------------------------------

    @action(detail=False, methods=['post'], url_path='from-devis')
    def from_devis(self, request):
        """
        POST /invoices/from-devis/
        Body : { "devis_id": 1 }
        """
        serializer = FactureFromDevisSerializer(
            data=request.data,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        facture = serializer.save()

        return Response(
            FactureSerializer(facture).data,
            status=status.HTTP_201_CREATED,
        )

    # -------------------------------------------------------------------------
    # Action : générer le PDF
    # -------------------------------------------------------------------------

    @action(detail=True, methods=['get'], url_path='pdf')
    def generer_pdf(self, request, pk=None):
        """
        GET /invoices/{id}/pdf/
        Génère et retourne le PDF de la facture.
        """
        facture = self.get_object()
        lignes = facture.lignes.all()

        # Adresse de facturation du client (fallback sur siège)
        adresse = (
            Adresse.objects
            .filter(client=facture.client, type=Adresse.TypeAdresse.FACTURATION)
            .first()
        ) or (
            Adresse.objects
            .filter(client=facture.client, type=Adresse.TypeAdresse.SIEGE)
            .first()
        )

        html = render_to_string('invoices/facture_pdf.html', {
            'facture': facture,
            'lignes': lignes,
            'adresse': adresse,
            'utilisateur': facture.utilisateur,
        })

        pdf = weasyprint.HTML(string=html).write_pdf()

        filename = f"{facture.numero or f'brouillon-{facture.pk}'}.pdf"
        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response