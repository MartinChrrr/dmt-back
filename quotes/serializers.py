from rest_framework import serializers
from django.db import transaction
from django.utils import timezone
from .models import Devis, LigneDevis, HistoriqueDevis


class LigneDevisSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)

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
        ]
        read_only_fields = ['montant_ht']


class HistoriqueDevisSerializer(serializers.ModelSerializer):
    class Meta:
        model = HistoriqueDevis
        fields = ['id', 'ancien_statut', 'nouveau_statut', 'created_at']
        read_only_fields = fields


class DevisSerializer(serializers.ModelSerializer):
    lignes = LigneDevisSerializer(many=True)
    historique = HistoriqueDevisSerializer(many=True, read_only=True)
    date_validite = serializers.DateField(required=False, allow_null=True)
    total_ht = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    total_tva = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    total_ttc = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = Devis
        fields = [
            'id',
            'utilisateur',
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
            'lignes',
            'historique',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['utilisateur', 'numero', 'created_at', 'updated_at']

    # -------------------------------------------------------------------------
    # Génération automatique du numéro de devis
    # -------------------------------------------------------------------------
    @staticmethod
    def _generer_numero(utilisateur):
        """
        Génère le numéro de devis à partir de la UserConfiguration.
        Format : PREFIXE-ANNEE-NUMERO (ex: DEV-2025-001)
        Incrémente next_quote_number de manière atomique.
        """
        from accounts.models import UserConfiguration

        config = UserConfiguration.objects.select_for_update().get(user=utilisateur)
        annee = timezone.now().year
        numero = f"{config.quote_prefix}-{annee}-{config.next_quote_number:03d}"
        config.next_quote_number += 1
        config.save(update_fields=['next_quote_number'])
        return numero

    # -------------------------------------------------------------------------
    # Création
    # -------------------------------------------------------------------------
    def create(self, validated_data):
        lignes_data = validated_data.pop('lignes', [])
        utilisateur = validated_data['utilisateur']

        with transaction.atomic():
            # Génération automatique du numéro
            validated_data['numero'] = self._generer_numero(utilisateur)

            # Auto-calcul de date_validite si non fournie
            if not validated_data.get('date_validite'):
                from accounts.models import UserConfiguration
                config = UserConfiguration.objects.get(user=utilisateur)
                date_emission = validated_data.get('date_emission', timezone.now().date())
                from datetime import timedelta
                validated_data['date_validite'] = date_emission + timedelta(days=config.quote_validity_days)

            devis = Devis.objects.create(**validated_data)

            for ligne_data in lignes_data:
                ligne_data.pop('id', None)
                ligne = LigneDevis(devis=devis, **ligne_data)
                ligne.save(recalculer_totaux=False)

            devis.calculer_totaux()

            # Historique de création
            HistoriqueDevis.objects.create(
                devis=devis,
                ancien_statut=None,
                nouveau_statut=devis.statut,
            )

        return devis

    # -------------------------------------------------------------------------
    # Mise à jour
    # -------------------------------------------------------------------------
    def update(self, instance, validated_data):
        lignes_data = validated_data.pop('lignes', [])

        # Détection changement de statut
        ancien_statut = instance.statut

        # Mise à jour des champs du devis
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # Historique si changement de statut
        if instance.statut != ancien_statut:
            HistoriqueDevis.objects.create(
                devis=instance,
                ancien_statut=ancien_statut,
                nouveau_statut=instance.statut,
            )

        # --- Gestion des lignes ---
        self._sync_lignes(instance, lignes_data)

        instance.calculer_totaux()
        return instance

    def _sync_lignes(self, devis, lignes_data):
        """
        Synchronise les lignes du devis :
        - Lignes avec id existant → mise à jour
        - Lignes sans id → création
        - Lignes existantes absentes du payload → soft delete
        """
        lignes_existantes = {
            ligne.id: ligne
            for ligne in devis.lignes.filter(deleted_at__isnull=True)
        }
        ids_recus = set()

        for ligne_data in lignes_data:
            ligne_id = ligne_data.pop('id', None)

            if ligne_id and ligne_id in lignes_existantes:
                # Mise à jour
                ligne = lignes_existantes[ligne_id]
                for attr, value in ligne_data.items():
                    setattr(ligne, attr, value)
                ligne.save(recalculer_totaux=False)
                ids_recus.add(ligne_id)
            else:
                # Création
                ligne = LigneDevis(devis=devis, **ligne_data)
                ligne.save(recalculer_totaux=False)

        # Soft delete des lignes absentes du payload
        ids_a_supprimer = set(lignes_existantes.keys()) - ids_recus
        if ids_a_supprimer:
            devis.lignes.filter(id__in=ids_a_supprimer).update(
                deleted_at=timezone.now()
            )

    # -------------------------------------------------------------------------
    # Validation
    # -------------------------------------------------------------------------
    def validate_lignes(self, value):
        if not value:
            raise serializers.ValidationError("Le devis doit contenir au moins une ligne.")
        return value

    def validate(self, data):
        date_emission = data.get('date_emission', getattr(self.instance, 'date_emission', None))
        date_validite = data.get('date_validite', getattr(self.instance, 'date_validite', None))

        if date_emission and date_validite and date_validite < date_emission:
            raise serializers.ValidationError({
                'date_validite': "La date de validité ne peut pas être antérieure à la date d'émission."
            })

        return data