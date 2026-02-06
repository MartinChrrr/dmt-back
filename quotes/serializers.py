from rest_framework import serializers
from .models import Devis, LigneDevis, HistoriqueDevis


class LigneDevisSerializer(serializers.ModelSerializer):
    class Meta:
        model = LigneDevis
        fields = [
            'id',
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
    # Lignes modifiables (en lecture ET écriture)
    lignes = LigneDevisSerializer(many=True, required=False)
    # Historique en lecture seule
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
    
    def create(self, validated_data):
        # Extraire les lignes des données
        lignes_data = validated_data.pop('lignes', [])
        
        devis = Devis.objects.create(**validated_data)
        
        for ligne_data in lignes_data:
            LigneDevis.objects.create(devis=devis, **ligne_data)
        
        # Les totaux sont calculés automatiquement par le modèle
        
        return devis
    
    def update(self, instance, validated_data):
        # Extraire les lignes des données
        lignes_data = validated_data.pop('lignes', None)
        
        # Mettre à jour les champs du devis
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        if lignes_data is not None:
            # Supprimer (soft delete) toutes les anciennes lignes
            instance.lignes.all().delete()
            
            for ligne_data in lignes_data:
                LigneDevis.objects.create(devis=instance, **ligne_data)
        
        # Les totaux sont recalculés automatiquement par le modèle
        
        return instance