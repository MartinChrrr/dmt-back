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
            'utilisateur',
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
            'utilisateur',
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
        
        # Créer le devis
        devis = Devis.objects.create(**validated_data)
        
        # Créer les lignes
        for ligne_data in lignes_data:
            LigneDevis.objects.create(devis=devis, **ligne_data)
        
        # Créer une entrée dans l'historique pour la création
        HistoriqueDevis.objects.create(
            devis=devis,
            ancien_statut=None,  # Pas d'ancien statut car c'est une création
            nouveau_statut=devis.statut  # Le statut initial du devis
        )
        
        # Vider le cache de la relation historique
        if hasattr(devis, '_prefetched_objects_cache'):
            delattr(devis, '_prefetched_objects_cache')


        # Les totaux sont calculés automatiquement par le modèle
        return devis
    
    def update(self, instance, validated_data):
        # Extraire les lignes des données
        lignes_data = validated_data.pop('lignes', None)
        
        # Détecter si le statut change
        ancien_statut = instance.statut
        nouveau_statut = validated_data.get('statut', ancien_statut)
        statut_change = ancien_statut != nouveau_statut
        
        # Mettre à jour les champs du devis
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        # Si le statut change, créer une entrée dans l'historique
        if statut_change:
            HistoriqueDevis.objects.create(
                devis=instance,
                ancien_statut=ancien_statut,
                nouveau_statut=nouveau_statut
            )
        
        if lignes_data is not None:
            # Supprimer (soft delete) toutes les anciennes lignes
            instance.lignes.all().delete()
            for ligne_data in lignes_data:
                LigneDevis.objects.create(devis=instance, **ligne_data)
        
        # Les totaux sont recalculés automatiquement par le modèle
        return instance