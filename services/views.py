from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from .models import Prestation
from .serializers import PrestationSerializer

class PrestationViewSet(viewsets.ModelViewSet):
    serializer_class = PrestationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Prestation.objects.filter(utilisateur=self.request.user)

    def perform_create(self, serializer):
        serializer.save(utilisateur=self.request.user)
