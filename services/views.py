from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from .models import Prestation
from .serializers import ServicesSerializer

class ServicesViewSet(viewsets.ModelViewSet):
    serializer_class = ServicesSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Prestation.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)