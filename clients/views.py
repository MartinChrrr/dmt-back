from django.shortcuts import render
from rest_framework import viewsets, status, filters
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied
from django_filters.rest_framework import DjangoFilterBackend

from .models import Client, Address
from .serializers import ClientSerializer, AddressSerializer


class ClientViewSet(viewsets.ModelViewSet):
    """Full CRUD for the connected user's clients"""
    queryset = Client.objects.all()
    serializer_class = ClientSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['raison_sociale', 'contact_nom', 'email', 'contact_email']
    ordering_fields = ['raison_sociale', 'created_at']
    ordering = ['raison_sociale']

    def get_queryset(self):
        """Returns only the connected user's clients"""
        return Client.objects.filter(utilisateur=self.request.user)

    def perform_create(self, serializer):
        """Automatically associates the client with the connected user"""
        serializer.save(utilisateur=self.request.user)


class AddressViewSet(viewsets.ModelViewSet):
    """Full CRUD for addresses of the connected user's clients"""
    queryset = Address.objects.all()
    serializer_class = AddressSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Returns only addresses of the connected user's clients"""
        queryset = Address.objects.filter(client__utilisateur=self.request.user)
        # Filter by client via ?client_id=X
        client_id = self.request.query_params.get('client_id')
        if client_id:
            queryset = queryset.filter(client_id=client_id)
        return queryset

    def perform_create(self, serializer):
        """Checks that the client belongs to the connected user"""
        client = serializer.validated_data['client']
        if client.utilisateur != self.request.user:
            raise PermissionDenied("This client does not belong to you")
        serializer.save()
