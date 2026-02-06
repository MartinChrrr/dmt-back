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
    
    serializer_class = DevisSerializer
    permission_classes = [IsAuthenticated]
    
    # Configuration des filtres et recherche
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['statut', 'client_id', 'utilisateur']
    search_fields = ['numero', 'objet']
    ordering_fields = ['date_emission', 'total_ttc', 'created_at']
    ordering = ['-date_emission']
    
    def get_queryset(self):
    # Retourne les devis non supprimés
        return Devis.objects.all()
    
    def destroy(self, request, pk=None):
    # Soft delete d'un devis
        devis = self.get_object()
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
        # Retourne les lignes non supprimées
        return LigneDevis.objects.all()
    
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
        # Retourne l'historique non supprimé
        return HistoriqueDevis.objects.all().order_by('-created_at')