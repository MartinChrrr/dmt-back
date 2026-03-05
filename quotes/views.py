from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters

from .models import Quote, QuoteLine, QuoteHistory
from .serializers import QuoteSerializer, QuoteLineSerializer, QuoteHistorySerializer


class QuoteViewSet(viewsets.ModelViewSet):
    queryset = Quote.objects.all()
    serializer_class = QuoteSerializer
    permission_classes = [IsAuthenticated]
    """
    API for managing quotes

    Available endpoints:
    - GET    /api/devis/                     -> List all quotes
    - POST   /api/devis/                     -> Create a quote
    - GET    /api/devis/{id}/                -> Quote detail
    - PUT    /api/devis/{id}/                -> Update a quote (full)
    - PATCH  /api/devis/{id}/                -> Update a quote (partial)
    - DELETE /api/devis/{id}/                -> Delete a quote (soft delete)
    - POST   /api/devis/{id}/changer_statut/ -> Change status
    """


    # Filter and search configuration
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['statut', 'client_id', 'utilisateur']
    search_fields = ['numero', 'objet']
    ordering_fields = ['date_emission', 'total_ttc', 'created_at']
    ordering = ['-date_emission']

    def get_queryset(self):
        return Quote.objects.filter(utilisateur=self.request.user)

    def perform_create(self, serializer):
        serializer.save(utilisateur=self.request.user)

    def update(self, request, *args, **kwargs):
        quote = self.get_object()
        if not quote.is_editable:
            return Response(
                {'error': 'Cannot modify a quote that is not in draft status.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        quote = self.get_object()
        if not quote.is_editable:
            return Response(
                {'error': 'Cannot modify a quote that is not in draft status.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request, pk=None):
        quote = self.get_object()
        if not quote.is_deletable:
            return Response(
                {'error': 'Cannot delete a quote that is not in draft status.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        quote.delete()
        return Response(
            {'message': 'Quote deleted successfully'},
            status=status.HTTP_204_NO_CONTENT
        )

    @action(detail=True, methods=['post'])
    def changer_statut(self, request, pk=None):
        # Change quote status and create a history entry

        # URL: POST /api/devis/{id}/changer_statut/
        # Body: {"statut": "ENVOYE"}

        quote = self.get_object()
        new_status = request.data.get('statut')

        # Check that the status is valid
        valid_statuses = [choice[0] for choice in Quote.STATUT_CHOICES]
        if new_status not in valid_statuses:
            return Response(
                {'error': 'Invalid status'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Save the old status
        old_status = quote.statut

        # Change the status
        quote.statut = new_status
        quote.save()

        # Create a history entry
        QuoteHistory.objects.create(
            devis=quote,
            ancien_statut=old_status,
            nouveau_statut=new_status
        )

        serializer = self.get_serializer(quote)
        return Response(
            {
                'message': 'Status changed successfully',
                'data': serializer.data
            },
            status=status.HTTP_200_OK
        )


class QuoteLineViewSet(viewsets.ModelViewSet):
    serializer_class = QuoteLineSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return QuoteLine.objects.filter(devis__utilisateur=self.request.user)

    def destroy(self, request, pk=None):
        # Soft delete a line
        line = self.get_object()
        line.delete()
        return Response(
            {'message': 'Line deleted successfully'},
            status=status.HTTP_204_NO_CONTENT
        )


class QuoteHistoryViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = QuoteHistorySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return QuoteHistory.objects.filter(devis__utilisateur=self.request.user).order_by('-created_at')
