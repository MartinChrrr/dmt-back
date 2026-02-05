from django.shortcuts import render
from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied 

from .models import Client, Adresse
from .serializers import ClientSerializer, AdresseSerializer


class ClientViewSet(viewsets.ModelViewSet):
    """CRUD complet pour les clients de l'utilisateur connecté"""
    queryset = Client.objects.all()
    serializer_class = ClientSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Retourne uniquement les clients de l'utilisateur connecté"""
        return Client.objects.filter(utilisateur=self.request.user)

    def perform_create(self, serializer):
        """Associe automatiquement le client à l'utilisateur connecté"""
        serializer.save(utilisateur=self.request.user)


class AdresseViewSet(viewsets.ModelViewSet):
    """CRUD complet pour les adresses des clients de l'utilisateur connecté"""
    queryset = Adresse.objects.all()
    serializer_class = AdresseSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Retourne uniquement les adresses des clients de l'utilisateur connecté"""
        queryset = Adresse.objects.filter(client__utilisateur=self.request.user)
        # Permet de filtrer par client via ?client_id=X
        client_id = self.request.query_params.get('client_id')
        if client_id:
            queryset = queryset.filter(client_id=client_id)
        return queryset

    def perform_create(self, serializer):
        """Vérifie que le client appartient bien à l'utilisateur connecté"""
        client = serializer.validated_data['client']
        if client.utilisateur != self.request.user:
            raise PermissionDenied("Ce client ne vous appartient pas")
        serializer.save()