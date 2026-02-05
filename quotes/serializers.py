# Serializers pour les devis
# Transforme les objets Python en JSON et vice-versa

from rest_framework import serializers
from .models import Devis, LigneDevis, HistoriqueDevis


class LigneDevisSerializer(serializers.ModelSerializer):
    class Meta:
        model = LigneDevis
        fields = [
            'id',
            'devis',
            'ordre',
            'libelle',
            'description',
            'quantite',
            'unite',
            'prix_unitaire_ht',
            'taux_tva',
            'montant_ht',
            'created_at',
        ]
        read_only_fields = ['id', 'montant_ht', 'created_at']


class HistoriqueDevisSerializer(serializers.ModelSerializer):
    class Meta:
        model = HistoriqueDevis
        fields = [
            'id',
            'devis',
            'ancien_statut',
            'nouveau_statut',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class DevisSerializer(serializers.ModelSerializer):
    # Inclure les relations (lignes et historique)
    lignes = LigneDevisSerializer(many=True, read_only=True)
    historique = HistoriqueDevisSerializer(many=True, read_only=True)
    
    class Meta:
        model = Devis
        fields = [
            'id',
            'utilisateur_id',
            'client_id',
            'numero',
            'date_emission',
            'date_validite',
            'statut',
            'objet',
            'notes',
            'total_ht',
            'total_tva',
            'total_ttc',
            'created_at',
            'updated_at',
            'lignes',
            'historique',
        ]
        read_only_fields = [
            'id',
            'numero',
            'total_ht',
            'total_tva',
            'total_ttc',
            'created_at',
            'updated_at',
        ]