from django.shortcuts import render

# Create your views here.

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters

from .models import Devis, LigneDevis, HistoriqueDevis
from .serializers import DevisSerializer, LigneDevisSerializer, HistoriqueDevisSerializer


class DevisViewSet(viewsets.ModelViewSet):
    queryset = Devis.objects.all()
    serializer_class = DevisSerializer
    permission_classes = [IsAuthenticated]
    """
    API pour gérer les devis
    
    Endpoints disponibles:
    - GET    /api/devis/                     -> Liste tous les devis
    - POST   /api/devis/                     -> Créer un devis
    - GET    /api/devis/{id}/                -> Détail d'un devis
    - PUT    /api/devis/{id}/                -> Modifier un devis (complet)
    - PATCH  /api/devis/{id}/                -> Modifier un devis (partiel)
    - DELETE /api/devis/{id}/                -> Supprimer un devis (soft delete)
    - POST   /api/devis/{id}/changer_statut/ -> Changer le statut
    """

    
    # Configuration des filtres et recherche
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['statut', 'client_id', 'utilisateur']
    search_fields = ['numero', 'objet']
    ordering_fields = ['date_emission', 'total_ttc', 'created_at']
    ordering = ['-date_emission']
    
    def get_queryset(self):
        return Devis.objects.filter(utilisateur=self.request.user)
    
    def perform_create(self, serializer):
        serializer.save(utilisateur=self.request.user)
    
    def update(self, request, *args, **kwargs):
        devis = self.get_object()
        if not devis.est_modifiable:
            return Response(
                {'error': 'Impossible de modifier un devis qui n\'est pas en brouillon.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        devis = self.get_object()
        if not devis.est_modifiable:
            return Response(
                {'error': 'Impossible de modifier un devis qui n\'est pas en brouillon.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request, pk=None):
        devis = self.get_object()
        if not devis.est_supprimable:
            return Response(
                {'error': 'Impossible de supprimer un devis qui n\'est pas en brouillon.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        devis.delete()
        return Response(
            {'message': 'Devis supprimé avec succès'},
            status=status.HTTP_204_NO_CONTENT
        )
    
    @action(detail=True, methods=['post'])
    def changer_statut(self, request, pk=None):
    # Change le statut d'un devis et crée une entrée dans l'historique
        
    # URL: POST /api/devis/{id}/changer_statut/
    # Body: {"statut": "ENVOYE"}

        devis = self.get_object()
        nouveau_statut = request.data.get('statut')
        
        # Vérifier que le statut est valide
        statuts_valides = [choix[0] for choix in Devis.STATUT_CHOICES]
        if nouveau_statut not in statuts_valides:
            return Response(
                {'error': 'Statut invalide'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Sauvegarder l'ancien statut
        ancien_statut = devis.statut
        
        # Changer le statut
        devis.statut = nouveau_statut
        devis.save()
        
        # Créer une entrée dans l'historique
        HistoriqueDevis.objects.create(
            devis=devis,
            ancien_statut=ancien_statut,
            nouveau_statut=nouveau_statut
        )
        
        serializer = self.get_serializer(devis)
        return Response(
            {
                'message': 'Statut modifié avec succès',
                'data': serializer.data
            },
            status=status.HTTP_200_OK
        )


class LigneDevisViewSet(viewsets.ModelViewSet):
    serializer_class = LigneDevisSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return LigneDevis.objects.filter(devis__utilisateur=self.request.user)
    
    def destroy(self, request, pk=None):
        # Soft delete d'une ligne
        ligne = self.get_object()
        ligne.delete()
        return Response(
            {'message': 'Ligne supprimée avec succès'},
            status=status.HTTP_204_NO_CONTENT
        )


class HistoriqueDevisViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = HistoriqueDevisSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return HistoriqueDevis.objects.filter(devis__utilisateur=self.request.user).order_by('-created_at')