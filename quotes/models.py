from datetime import date
from django.db import models
from django.utils import timezone
from decimal import Decimal
from django.conf import settings


# SOFT DELETE

class SoftDeleteManager(models.Manager):
    # Manager that automatically excludes deleted objects
    def get_queryset(self):
        return super().get_queryset().filter(deleted_at__isnull=True)


class SoftDeleteModel(models.Model):
    # Abstract model for soft delete
    deleted_at = models.DateTimeField(null=True, blank=True, verbose_name="Date de suppression")

    objects = SoftDeleteManager()
    all_objects = models.Manager()

    class Meta:
        abstract = True

    def delete(self, *args, **kwargs):
        # Soft delete: mark as deleted
        self.deleted_at = timezone.now()
        self.save()


# QUOTE

class Quote(SoftDeleteModel):
    # Quote issued by the user
    STATUT_BROUILLON = 'BROUILLON'
    STATUT_ENVOYE = 'ENVOYE'
    STATUT_ACCEPTE = 'ACCEPTE'
    STATUT_REFUSE = 'REFUSE'
    STATUT_EXPIRE = 'EXPIRE'

    STATUT_CHOICES = [
        (STATUT_BROUILLON, 'Draft'),
        (STATUT_ENVOYE, 'Sent'),
        (STATUT_ACCEPTE, 'Accepted'),
        (STATUT_REFUSE, 'Refused'),
        (STATUT_EXPIRE, 'Expired'),
    ]

    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='devis',
        verbose_name='Utilisateur'
    )
    client = models.ForeignKey(
        'clients.Client',
        on_delete=models.PROTECT,
        related_name='devis',
        verbose_name='Client'
    )
    numero = models.CharField(max_length=50, unique=True, blank=True, verbose_name='Numéro')
    date_emission = models.DateField(default=date.today, verbose_name='Date d\'émission')
    date_validite = models.DateField(null=True, blank=True, verbose_name='Date de validité')
    statut = models.CharField(
        max_length=20,
        choices=STATUT_CHOICES,
        default=STATUT_BROUILLON,
        verbose_name='Statut'
    )
    objet = models.CharField(max_length=255, blank=True, verbose_name='Objet')
    notes = models.TextField(blank=True, verbose_name='Notes')
    total_ht = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name='Total HT')
    total_tva = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name='Total TVA')
    total_ttc = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name='Total TTC')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'devis'
        ordering = ['-date_emission', '-created_at']
        verbose_name = 'Devis'
        verbose_name_plural = 'Devis'

    def __str__(self):
        return f"{self.numero}"

    @property
    def is_editable(self):
        return self.statut == self.STATUT_BROUILLON

    @property
    def is_deletable(self):
        return self.statut == self.STATUT_BROUILLON

    def save(self, *args, **kwargs):
        # Automatically generate the number if empty
        if not self.numero:
            self.numero = self._generate_number()
        super().save(*args, **kwargs)

    def _generate_number(self):
        from datetime import datetime
        from accounts.models import UserConfiguration

        config, _ = UserConfiguration.objects.get_or_create(user=self.utilisateur)
        prefix = config.quote_prefix
        year = datetime.now().year
        number = f"{prefix}-{year}-{config.next_quote_number:03d}"
        config.next_quote_number += 1
        config.save()
        return number

    def calculate_totals(self):
        # Calculate totals: excl. tax, VAT and incl. tax
        lines = self.lignes.filter(deleted_at__isnull=True)

        self.total_ht = sum(line.montant_ht for line in lines) or Decimal('0.00')
        self.total_tva = sum(line.montant_ht * (line.taux_tva / 100) for line in lines) or Decimal('0.00')
        self.total_ttc = self.total_ht + self.total_tva
        self.save()

    def delete(self, *args, **kwargs):
        if not self.is_deletable:
            raise ValueError("Cannot delete a quote that is not in draft status.")
        # Cascading soft delete
        for line in self.lignes.all():
            line.delete()
        for history in self.historique.all():
            history.delete()
        super().delete(*args, **kwargs)


class QuoteLine(SoftDeleteModel):
    # Line of a quote
    devis = models.ForeignKey(
        Quote,
        on_delete=models.CASCADE,
        related_name='lignes',
        verbose_name='Devis'
    )
    ordre = models.IntegerField(default=0, verbose_name='Ordre')
    libelle = models.CharField(max_length=255, verbose_name='Libellé')
    description = models.TextField(blank=True, verbose_name='Description')
    quantite = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('1.00'),
        verbose_name='Quantité'
    )
    unite = models.CharField(max_length=20, blank=True, verbose_name='Unité')
    prix_unitaire_ht = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name='Prix unitaire HT'
    )
    taux_tva = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('20.00'),
        verbose_name='Taux TVA (%)'
    )
    montant_ht = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name='Montant HT'
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'lignes_devis'
        ordering = ['ordre', 'id']
        verbose_name = 'Ligne de devis'
        verbose_name_plural = 'Lignes de devis'

    def __str__(self):
        return f"{self.devis.numero} - {self.libelle}"

    def save(self, *args, **kwargs):
        # Calculate the excl. tax amount and update quote totals
        self.montant_ht = self.quantite * self.prix_unitaire_ht
        super().save(*args, **kwargs)
        self.devis.calculate_totals()

    def delete(self, *args, **kwargs):
        # Soft delete and recalculate totals
        quote = self.devis
        super().delete(*args, **kwargs)
        quote.calculate_totals()


class QuoteHistory(SoftDeleteModel):
    # Status change history
    devis = models.ForeignKey(
        Quote,
        on_delete=models.CASCADE,
        related_name='historique',
        verbose_name='Devis'
    )
    ancien_statut = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        verbose_name='Ancien statut'
    )
    nouveau_statut = models.CharField(max_length=20, verbose_name='Nouveau statut')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'historique_devis'
        ordering = ['-created_at']
        verbose_name = 'Historique de devis'
        verbose_name_plural = 'Historiques de devis'

    def __str__(self):
        if self.ancien_statut:
            return f"{self.devis.numero} - {self.ancien_statut} → {self.nouveau_statut}"
        return f"{self.devis.numero} - Creation"
