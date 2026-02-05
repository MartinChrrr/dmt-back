from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend, FilterSet, DateFromToRangeFilter
from .models import Devis, HistoriqueDevis
from .serializers import DevisSerializer


# -------------------------------------------------------------------------
# Filtres
# -------------------------------------------------------------------------

class DevisFilter(FilterSet):
    date_emission = DateFromToRangeFilter()

    class Meta:
        model = Devis
        fields = {
            'client': ['exact'],
            'statut': ['exact'],
        }


# -------------------------------------------------------------------------
# ViewSet
# -------------------------------------------------------------------------

class DevisViewSet(viewsets.ModelViewSet):
    """
    CRUD complet sur les devis avec lignes imbriquées.

    list:       GET    /devis/
    create:     POST   /devis/
    retrieve:   GET    /devis/{id}/
    update:     PUT    /devis/{id}/
    partial:    PATCH  /devis/{id}/
    delete:     DELETE /devis/{id}/
    changer_statut: POST /devis/{id}/changer-statut/
    """

    serializer_class = DevisSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_class = DevisFilter
    ordering_fields = ['date_emission', 'created_at', 'total_ttc']
    ordering = ['-date_emission', '-created_at']

    def get_queryset(self):
        return (
            Devis.objects
            .filter(utilisateur=self.request.user)
            .prefetch_related('lignes', 'historique')
        )

    def perform_create(self, serializer):
        serializer.save(utilisateur=self.request.user)

    def perform_destroy(self, instance):
        """Soft delete via le modèle"""
        instance.delete()

    # -------------------------------------------------------------------------
    # Action : changement de statut
    # -------------------------------------------------------------------------

    TRANSITIONS = {
        Devis.STATUT_BROUILLON: [Devis.STATUT_ENVOYE],
        Devis.STATUT_ENVOYE: [Devis.STATUT_ACCEPTE, Devis.STATUT_REFUSE, Devis.STATUT_EXPIRE],
        Devis.STATUT_ACCEPTE: [],
        Devis.STATUT_REFUSE: [Devis.STATUT_BROUILLON],
        Devis.STATUT_EXPIRE: [Devis.STATUT_BROUILLON],
    }

    @action(detail=True, methods=['post'], url_path='changer-statut')
    def changer_statut(self, request, pk=None):
        """
        POST /devis/{id}/changer-statut/
        Body : { "statut": "ENVOYE" }
        """
        devis = self.get_object()
        nouveau_statut = request.data.get('statut')

        if not nouveau_statut:
            return Response(
                {'statut': "Ce champ est requis."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        transitions_possibles = self.TRANSITIONS.get(devis.statut, [])
        if nouveau_statut not in transitions_possibles:
            return Response(
                {
                    'statut': (
                        f"Transition de « {devis.statut} » vers « {nouveau_statut} » "
                        f"non autorisée. Transitions possibles : {transitions_possibles}"
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        ancien_statut = devis.statut
        devis.statut = nouveau_statut
        devis.save(update_fields=['statut'])

        HistoriqueDevis.objects.create(
            devis=devis,
            ancien_statut=ancien_statut,
            nouveau_statut=nouveau_statut,
        )

        serializer = self.get_serializer(devis)
        return Response(serializer.data)