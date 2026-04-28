from rest_framework import serializers
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
from .models import Invoice, InvoiceLine, InvoiceHistory
from clients.models import Client
from clients.serializers import ClientSerializer


class InvoiceLineSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)

    class Meta:
        model = InvoiceLine
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


class InvoiceHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = InvoiceHistory
        fields = ['id', 'ancien_statut', 'nouveau_statut', 'created_at']
        read_only_fields = fields


class InvoiceSerializer(serializers.ModelSerializer):
    client = ClientSerializer(read_only=True)
    client_id = serializers.PrimaryKeyRelatedField(
        queryset=Client.objects.all(),
        source='client',
        write_only=True,
    )
    lignes = InvoiceLineSerializer(many=True)
    historique = InvoiceHistorySerializer(many=True, read_only=True)
    date_echeance = serializers.DateField(required=False, allow_null=True)
    total_ht = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    total_tva = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    total_ttc = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = Invoice
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

    # Creation
    def create(self, validated_data):
        lines_data = validated_data.pop('lignes', [])
        user = validated_data['utilisateur']

        with transaction.atomic():
            # Auto-calculate due date if not provided
            if not validated_data.get('date_echeance'):
                from accounts.models import UserConfiguration
                config = UserConfiguration.objects.get(user=user)
                date_emission = validated_data.get('date_emission', timezone.now().date())
                
                validated_data['date_echeance'] = date_emission + timedelta(days=config.payment_deadline_days)

            invoice = Invoice.objects.create(**validated_data)

            for line_data in lines_data:
                line_data.pop('id', None)
                line = InvoiceLine(facture=invoice, **line_data)
                line.save(recalculate_totals=False)

            invoice.calculate_totals()

            InvoiceHistory.objects.create(
                facture=invoice,
                ancien_statut=None,
                nouveau_statut=invoice.statut,
            )

        return invoice

    # Update (only if DRAFT)
    def update(self, instance, validated_data):
        if not instance.is_editable:
            raise serializers.ValidationError(
                "Only a draft invoice can be modified."
            )

        # Client cannot be changed after creation
        validated_data.pop('client', None)

        lines_data = validated_data.pop('lignes', [])

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        self._sync_lines(instance, lines_data)
        instance.calculate_totals()
        return instance

    def _sync_lines(self, invoice, lines_data):
        """
        Synchronize invoice lines:
        - Lines with existing id → update
        - Lines without id → create
        - Existing lines absent from payload → delete (hard delete)
        """
        existing_lines = {
            line.id: line
            for line in invoice.lignes.all()
        }
        received_ids = set()

        for line_data in lines_data:
            line_id = line_data.pop('id', None)

            if line_id and line_id in existing_lines:
                line = existing_lines[line_id]
                for attr, value in line_data.items():
                    setattr(line, attr, value)
                line.save(recalculate_totals=False)
                received_ids.add(line_id)
            else:
                line = InvoiceLine(facture=invoice, **line_data)
                line.save(recalculate_totals=False)

        # Hard delete absent lines
        ids_to_delete = set(existing_lines.keys()) - received_ids
        if ids_to_delete:
            invoice.lignes.filter(id__in=ids_to_delete).delete()

    # Validation
    def validate_lignes(self, value):
        if not value:
            raise serializers.ValidationError("The invoice must contain at least one line.")
        return value

    def validate(self, data):
        date_emission = data.get('date_emission', getattr(self.instance, 'date_emission', None))
        date_echeance = data.get('date_echeance', getattr(self.instance, 'date_echeance', None))

        if date_emission and date_echeance and date_echeance < date_emission:
            raise serializers.ValidationError({
                'date_echeance': "The due date cannot be earlier than the issue date."
            })

        return data


# Serializer for creating an invoice from an accepted quote

class InvoiceFromQuoteSerializer(serializers.Serializer):
    """Create an invoice from an accepted quote"""
    devis_id = serializers.IntegerField()

    def validate_devis_id(self, value):
        from quotes.models import Quote
        try:
            quote = Quote.objects.get(id=value)
        except Quote.DoesNotExist:
            raise serializers.ValidationError("Quote not found.")

        if quote.statut not in (Quote.STATUT_ENVOYE, Quote.STATUT_ACCEPTE):
            raise serializers.ValidationError(
                "Only a sent or accepted quote can be converted to an invoice."
            )

        if hasattr(quote, 'facture') and quote.facture and quote.facture.deleted_at is None:
            raise serializers.ValidationError("This quote has already been converted to an invoice.")

        self.quote = quote
        return value

    def create(self, validated_data):
        from quotes.models import QuoteHistory

        quote = self.quote
        user = self.context['request'].user

        with transaction.atomic():
            # Set quote to ACCEPTED if not already
            if quote.statut != quote.STATUT_ACCEPTE:
                old_status = quote.statut
                quote.statut = quote.STATUT_ACCEPTE
                quote.save(update_fields=['statut'])
                QuoteHistory.objects.create(
                    devis=quote,
                    ancien_statut=old_status,
                    nouveau_statut=quote.STATUT_ACCEPTE,
                )

            from accounts.models import UserConfiguration
            config = UserConfiguration.objects.get(user=user)

            date_emission = timezone.now().date()
            date_echeance = date_emission + timedelta(days=config.payment_deadline_days)

            invoice = Invoice.objects.create(
                utilisateur=user,
                client=quote.client,
                devis_origine=quote,
                date_emission=date_emission,
                date_echeance=date_echeance,
                objet=quote.objet,
                notes=quote.notes,
            )

            # Copy lines from the quote
            for quote_line in quote.lignes.filter(deleted_at__isnull=True):
                InvoiceLine(
                    facture=invoice,
                    ordre=quote_line.ordre,
                    libelle=quote_line.libelle,
                    description=quote_line.description,
                    quantite=quote_line.quantite,
                    unite=quote_line.unite,
                    prix_unitaire_ht=quote_line.prix_unitaire_ht,
                    taux_tva=quote_line.taux_tva,
                ).save(recalculate_totals=False)

            invoice.calculate_totals()

            InvoiceHistory.objects.create(
                facture=invoice,
                ancien_statut=None,
                nouveau_statut=Invoice.STATUT_BROUILLON,
            )

            # Set invoice to SENT with number generation
            from invoices.views import InvoiceViewSet
            invoice.numero = InvoiceViewSet._generate_number(user)
            invoice.statut = Invoice.STATUT_ENVOYEE
            invoice.save(update_fields=['statut', 'numero'])

            InvoiceHistory.objects.create(
                facture=invoice,
                ancien_statut=Invoice.STATUT_BROUILLON,
                nouveau_statut=Invoice.STATUT_ENVOYEE,
            )

        return invoice
