from rest_framework.routers import DefaultRouter
from .views import FactureViewSet

router = DefaultRouter()
router.register('invoices', FactureViewSet, basename='facture')

urlpatterns = router.urls