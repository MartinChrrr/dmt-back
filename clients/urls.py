from django.urls import include, path
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'clients', views.ClientViewSet, basename='client')
router.register(r'adresses', views.AdresseViewSet, basename='adresse')

print(router.get_urls()) 

urlpatterns = [
    path('', include(router.urls)),
]