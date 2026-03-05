from django.contrib import admin
from .models import Service

@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ['label', 'utilisateur', 'unit_price_excl_tax', 'unit', 'taux_tva', 'created_at']
    list_filter = ['unit', 'taux_tva']
    search_fields = ['label', 'description']
