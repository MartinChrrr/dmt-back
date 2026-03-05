from rest_framework import serializers
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
from .models import Facture, LigneFacture, HistoriqueFacture
from clients.models import Client
from clients.serializers import ClientSerializer


class LigneFactureSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)

    class Meta:
        model = LigneFacture
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


class HistoriqueFactureSerializer(serializers.ModelSerializer):
    class Meta:
        model = HistoriqueFacture
        fields = ['id', 'ancien_statut', 'nouveau_statut', 'created_at']
        read_only_fields = fields


class FactureSerializer(serializers.ModelSerializer):
    client = ClientSerializer(read_only=True)
    client_id = serializers.PrimaryKeyRelatedField(
        queryset=Client.objects.all(),
        source='client',
        write_only=True,
    )
    lignes = LigneFactureSerializer(many=True)
    historique = HistoriqueFactureSerializer(many=True, read_only=True)
    date_echeance = serializers.DateField(required=False, allow_null=True)
    total_ht = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    total_tva = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    total_ttc = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = Facture
        fields = [
            'id',
            'utilisateur',
            'client',
            'client_id',
            'devis_origine',
            'numero',
            'date_emission',
            'date_echeance',
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
        read_only_fields = ['utilisateur', 'numero', 'statut', 'created_at', 'updated_at']

    # -------------------------------------------------------------------------
    # Création
    # -------------------------------------------------------------------------
    def create(self, validated_data):
        lignes_data = validated_data.pop('lignes', [])
        utilisateur = validated_data['utilisateur']

        with transaction.atomic():
            # Auto-calcul de date_echeance si non fournie
            if not validated_data.get('date_echeance'):
                from accounts.models import UserConfiguration
                config = UserConfiguration.objects.get(user=utilisateur)
                date_emission = validated_data.get('date_emission', timezone.now().date())
                validated_data['date_echeance'] = date_emission + timedelta(days=config.payment_deadline_days)

            facture = Facture.objects.create(**validated_data)

            for ligne_data in lignes_data:
                ligne_data.pop('id', None)
                ligne = LigneFacture(facture=facture, **ligne_data)
                ligne.save(recalculer_totaux=False)

            facture.calculer_totaux()

            HistoriqueFacture.objects.create(
                facture=facture,
                ancien_statut=None,
                nouveau_statut=facture.statut,
            )

        return facture

    # -------------------------------------------------------------------------
    # Mise à jour (uniquement si BROUILLON)
    # -------------------------------------------------------------------------
    def update(self, instance, validated_data):
        if not instance.est_modifiable:
            raise serializers.ValidationError(
                "Seule une facture en brouillon peut être modifiée."
            )

        lignes_data = validated_data.pop('lignes', [])

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        self._sync_lignes(instance, lignes_data)
        instance.calculer_totaux()
        return instance

    def _sync_lignes(self, facture, lignes_data):
        """
        Synchronise les lignes de la facture :
        - Lignes avec id existant → mise à jour
        - Lignes sans id → création
        - Lignes existantes absentes du payload → suppression (hard delete)
        """
        lignes_existantes = {
            ligne.id: ligne
            for ligne in facture.lignes.all()
        }
        ids_recus = set()

        for ligne_data in lignes_data:
            ligne_id = ligne_data.pop('id', None)

            if ligne_id and ligne_id in lignes_existantes:
                ligne = lignes_existantes[ligne_id]
                for attr, value in ligne_data.items():
                    setattr(ligne, attr, value)
                ligne.save(recalculer_totaux=False)
                ids_recus.add(ligne_id)
            else:
                ligne = LigneFacture(facture=facture, **ligne_data)
                ligne.save(recalculer_totaux=False)

        # Hard delete des lignes absentes
        ids_a_supprimer = set(lignes_existantes.keys()) - ids_recus
        if ids_a_supprimer:
            facture.lignes.filter(id__in=ids_a_supprimer).delete()

    # -------------------------------------------------------------------------
    # Validation
    # -------------------------------------------------------------------------
    def validate_lignes(self, value):
        if not value:
            raise serializers.ValidationError("La facture doit contenir au moins une ligne.")
        return value

    def validate(self, data):
        date_emission = data.get('date_emission', getattr(self.instance, 'date_emission', None))
        date_echeance = data.get('date_echeance', getattr(self.instance, 'date_echeance', None))

        if date_emission and date_echeance and date_echeance < date_emission:
            raise serializers.ValidationError({
                'date_echeance': "La date d'échéance ne peut pas être antérieure à la date d'émission."
            })

        return data


# -------------------------------------------------------------------------
# Serializer de création depuis un devis accepté
# -------------------------------------------------------------------------

class FactureFromDevisSerializer(serializers.Serializer):
    """Crée une facture à partir d'un devis accepté"""
    devis_id = serializers.IntegerField()

    def validate_devis_id(self, value):
        from quotes.models import Devis
        try:
            devis = Devis.objects.get(id=value)
        except Devis.DoesNotExist:
            raise serializers.ValidationError("Devis introuvable.")

        if devis.statut != Devis.STATUT_ACCEPTE:
            raise serializers.ValidationError("Seul un devis accepté peut être transformé en facture.")

        if hasattr(devis, 'facture') and devis.facture and devis.facture.deleted_at is None:
            raise serializers.ValidationError("Ce devis a déjà été transformé en facture.")

        self.devis = devis
        return value

    def create(self, validated_data):
        devis = self.devis
        utilisateur = self.context['request'].user

        with transaction.atomic():
            from accounts.models import UserConfiguration
            config = UserConfiguration.objects.get(user=utilisateur)

            date_emission = timezone.now().date()
            date_echeance = date_emission + timedelta(days=config.payment_deadline_days)

            facture = Facture.objects.create(
                utilisateur=utilisateur,
                client=devis.client,
                devis_origine=devis,
                date_emission=date_emission,
                date_echeance=date_echeance,
                objet=devis.objet,
                notes=devis.notes,
            )

            # Copier les lignes du devis
            for ligne_devis in devis.lignes.filter(deleted_at__isnull=True):
                LigneFacture(
                    facture=facture,
                    ordre=ligne_devis.ordre,
                    libelle=ligne_devis.libelle,
                    description=ligne_devis.description,
                    quantite=ligne_devis.quantite,
                    unite=ligne_devis.unite,
                    prix_unitaire_ht=ligne_devis.prix_unitaire_ht,
                    taux_tva=ligne_devis.taux_tva,
                ).save(recalculer_totaux=False)

            facture.calculer_totaux()

            HistoriqueFacture.objects.create(
                facture=facture,
                ancien_statut=None,
                nouveau_statut=Facture.STATUT_BROUILLON,
            )

        return facture