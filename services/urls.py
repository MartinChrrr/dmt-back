from rest_framework.routers import DefaultRouter
from .views import ServicesViewSet

router = DefaultRouter()
router.register(r'services', ServicesViewSet, basename='services')

urlpatterns = router.urls