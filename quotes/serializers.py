from datetime import timedelta
from rest_framework import serializers
from clients.serializers import ClientSerializer
from clients.models import Client
from accounts.models import UserConfiguration
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
    # Modifiable lines (read AND write)
    lignes = LigneDevisSerializer(many=True, required=False)
    # Read-only history
    historique = HistoriqueDevisSerializer(many=True, read_only=True)

    # Utilisateur assigné automatiquement via le token (read-only)
    utilisateur = serializers.PrimaryKeyRelatedField(read_only=True)

    # Afficher les données complètes du client en lecture
    client = ClientSerializer(read_only=True)

    # Accepter l'ID du client en écriture
    client_id = serializers.PrimaryKeyRelatedField(
        queryset=Client.objects.all(),
        source='client',
        write_only=True
    )
    

    class Meta:
        model = Devis
        fields = [
            'id',
            'utilisateur',
            'client_id',
            'client',
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
        # Extract data rows
        lignes_data = validated_data.pop('lignes', [])

        # Auto-calculer date_validite si non fournie
        if not validated_data.get('date_validite'):
            user = validated_data['utilisateur']
            config, _ = UserConfiguration.objects.get_or_create(user=user)
            date_emission = validated_data.get('date_emission') or Devis._meta.get_field('date_emission').default()
            validated_data['date_validite'] = date_emission + timedelta(days=config.quote_validity_days)

        # Create the quotation
        devis = Devis.objects.create(**validated_data)
        
        # Create the lines
        for ligne_data in lignes_data:
            LigneDevis.objects.create(devis=devis, **ligne_data)
        
        # Create an entry in the history for the creation
        HistoriqueDevis.objects.create(
            devis=devis,
            ancien_statut=None,  # No previous status as it is a new creation
            nouveau_statut=devis.statut  # The initial status of the quotation
        )
        
        # Clear the cache of the historical relationship
        if hasattr(devis, '_prefetched_objects_cache'):
            delattr(devis, '_prefetched_objects_cache')


        # Totals are calculated automatically by the model.
        return devis
    
    def update(self, instance, validated_data):
        # Le client ne peut pas être changé après création
        validated_data.pop('client', None)

        # Extract data lines
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