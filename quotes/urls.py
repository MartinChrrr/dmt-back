from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import DevisViewSet, LigneDevisViewSet, HistoriqueDevisViewSet

router = DefaultRouter()

router.register('', DevisViewSet, basename='devis')
# router.register(r'lignes-devis', LigneDevisViewSet, basename='ligne-devis')
# router.register(r'historique-devis', HistoriqueDevisViewSet, basename='historique-devis')

urlpatterns = [
    path('', include(router.urls)),
]