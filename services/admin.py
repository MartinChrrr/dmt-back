from django.contrib import admin
from .models import Prestation

@admin.register(Prestation)
class PrestationAdmin(admin.ModelAdmin):
    list_display = ['label', 'utilisateur', 'unit_price_excl_tax', 'unit', 'taux_tva', 'created_at']
    list_filter = ['unit', 'taux_tva']
    search_fields = ['label', 'description']
