from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import QuoteViewSet, QuoteLineViewSet, QuoteHistoryViewSet

router = DefaultRouter()

router.register('quotes', QuoteViewSet, basename='devis')
# router.register(r'lignes-devis', QuoteLineViewSet, basename='ligne-devis')
# router.register(r'historique-devis', QuoteHistoryViewSet, basename='historique-devis')

urlpatterns = [
    path('', include(router.urls)),
]
