from rest_framework.routers import DefaultRouter
from .views import DevisViewSet

router = DefaultRouter()
router.register('', DevisViewSet, basename='devis')

urlpatterns = router.urls