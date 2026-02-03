from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from . import views

urlpatterns = [
    path('register/', views.register, name='register'),
    path('login/', TokenObtainPairView.as_view(), name='login'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('logout/', views.logout, name='logout'),
    path('me/', views.current_user, name='current-user'),
    path('profile/', views.user_profile, name='user-profile'),
    path('configuration/', views.UserConfigurationView.as_view(), name='user-configuration'),
]