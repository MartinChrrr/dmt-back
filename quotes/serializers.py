from datetime import date, timedelta
from rest_framework import serializers
from clients.serializers import ClientSerializer
from clients.models import Client
from accounts.models import UserConfiguration
from .models import Quote, QuoteLine, QuoteHistory


class QuoteLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuoteLine
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


class QuoteHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = QuoteHistory
        fields = [
            'id',
            'devis',
            'ancien_statut',
            'nouveau_statut',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class QuoteSerializer(serializers.ModelSerializer):
    # Modifiable lines (read AND write)
    lignes = QuoteLineSerializer(many=True, required=False)
    # Read-only history
    historique = QuoteHistorySerializer(many=True, read_only=True)

    # User automatically assigned via token (read-only)
    utilisateur = serializers.PrimaryKeyRelatedField(read_only=True)

    # Display full client data on read
    client = ClientSerializer(read_only=True)

    # Accept client ID on write
    client_id = serializers.PrimaryKeyRelatedField(
        queryset=Client.objects.all(),
        source='client',
        write_only=True
    )


    class Meta:
        model = Quote
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
        # Extract line data
        lines_data = validated_data.pop('lignes', [])

        # Auto-calculate validity date if not provided
        if not validated_data.get('date_validite'):
            user = validated_data['utilisateur']
            config, _ = UserConfiguration.objects.get_or_create(user=user)
            date_emission = validated_data.get('date_emission') or date.today()
            validated_data['date_validite'] = date_emission + timedelta(days=config.quote_validity_days)

        # Create the quote
        quote = Quote.objects.create(**validated_data)

        # Create the lines
        for line_data in lines_data:
            QuoteLine.objects.create(devis=quote, **line_data)

        # Create a history entry for the creation
        QuoteHistory.objects.create(
            devis=quote,
            ancien_statut=None,  # No previous status as it is a new creation
            nouveau_statut=quote.statut  # The initial status of the quote
        )

        # Clear the cache of the history relationship
        if hasattr(quote, '_prefetched_objects_cache'):
            delattr(quote, '_prefetched_objects_cache')


        # Totals are calculated automatically by the model
        return quote

    def update(self, instance, validated_data):
        # Client cannot be changed after creation
        validated_data.pop('client', None)

        # Extract line data
        lines_data = validated_data.pop('lignes', None)

        # Detect if status changes
        old_status = instance.statut
        new_status = validated_data.get('statut', old_status)
        status_changed = old_status != new_status

        # Update quote fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # If status changed, create a history entry
        if status_changed:
            QuoteHistory.objects.create(
                devis=instance,
                ancien_statut=old_status,
                nouveau_statut=new_status
            )

        if lines_data is not None:
            # Soft delete all previous lines
            instance.lignes.all().delete()
            for line_data in lines_data:
                QuoteLine.objects.create(devis=instance, **line_data)

        # Totals are recalculated automatically by the model
        return instance
