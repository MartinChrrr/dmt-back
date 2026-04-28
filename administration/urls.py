from django.urls import path

from .views import AdminUserDeleteView, AdminUserExportView, AdminUserListView

urlpatterns = [
    path('admin/users/', AdminUserListView.as_view(), name='admin-user-list'),
    path('admin/users/<int:user_id>/', AdminUserDeleteView.as_view(), name='admin-user-delete'),
    path('admin/users/<int:user_id>/export/', AdminUserExportView.as_view(), name='admin-user-export'),
]
