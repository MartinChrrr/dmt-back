from rest_framework.routers import DefaultRouter
from .views import PrestationViewSet

router = DefaultRouter()
router.register(r'services', PrestationViewSet, basename='services')

urlpatterns = router.urls
