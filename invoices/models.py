from datetime import date
from django.conf import settings
from django.db import models
from django.utils import timezone
from decimal import Decimal


# -------------------------------------------------------------------------
# SOFT DELETE (reusable — eventually to be shared in a common module)
# -------------------------------------------------------------------------

class SoftDeleteManager(models.Manager):
    """Manager that automatically excludes deleted objects"""
    def get_queryset(self):
        return super().get_queryset().filter(deleted_at__isnull=True)


class SoftDeleteModel(models.Model):
    """Abstract model for soft delete"""
    deleted_at = models.DateTimeField(null=True, blank=True, verbose_name="Date de suppression")

    objects = SoftDeleteManager()
    all_objects = models.Manager()

    class Meta:
        abstract = True

    def delete(self, *args, **kwargs):
        """Soft delete: mark as deleted"""
        self.deleted_at = timezone.now()
        self.save(update_fields=['deleted_at'])


# -------------------------------------------------------------------------
# INVOICE
# -------------------------------------------------------------------------

class Invoice(SoftDeleteModel):
    """Invoice issued by the user"""
    STATUT_BROUILLON = 'BROUILLON'
    STATUT_ENVOYEE = 'ENVOYEE'
    STATUT_PAYEE = 'PAYEE'
    STATUT_EN_RETARD = 'EN_RETARD'

    STATUT_CHOICES = [
        (STATUT_BROUILLON, 'Draft'),
        (STATUT_ENVOYEE, 'Sent'),
        (STATUT_PAYEE, 'Paid'),
        (STATUT_EN_RETARD, 'Overdue'),
    ]

    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='factures',
        verbose_name='Utilisateur',
    )
    client = models.ForeignKey(
        'clients.Client',
        on_delete=models.CASCADE,
        related_name='factures',
        verbose_name='Client',
    )
    devis_origine = models.OneToOneField(
        'quotes.Quote',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='facture',
        verbose_name='Devis d\'origine',
    )
    numero = models.CharField(
        max_length=50,
        unique=True,
        null=True,
        blank=True,
        verbose_name='Numéro',
    )
    date_emission = models.DateField(default=date.today, verbose_name="Date d'émission")
    date_echeance = models.DateField(verbose_name='Date d\'échéance')
    statut = models.CharField(
        max_length=20,
        choices=STATUT_CHOICES,
        default=STATUT_BROUILLON,
        verbose_name='Statut',
    )
    objet = models.CharField(max_length=255, blank=True, verbose_name='Objet')
    notes = models.TextField(blank=True, verbose_name='Notes')
    total_ht = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name='Total HT')
    total_tva = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name='Total TVA')
    total_ttc = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name='Total TTC')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'factures'
        ordering = ['-date_emission', '-created_at']
        verbose_name = 'Facture'
        verbose_name_plural = 'Factures'

    def __str__(self):
        return self.numero or f"Draft #{self.pk}"

    @property
    def is_editable(self):
        return self.statut == self.STATUT_BROUILLON

    @property
    def is_deletable(self):
        return self.statut == self.STATUT_BROUILLON

    def calculate_totals(self):
        """Calculate totals: excl. tax, VAT and incl. tax from lines"""
        lines = list(self.lignes.all())

        self.total_ht = sum((line.montant_ht for line in lines), Decimal('0.00'))
        self.total_tva = sum(
            (line.montant_ht * line.taux_tva / Decimal('100') for line in lines),
            Decimal('0.00'),
        )
        self.total_ttc = self.total_ht + self.total_tva
        self.save(update_fields=['total_ht', 'total_tva', 'total_ttc'])

    def delete(self, *args, **kwargs):
        """Soft delete — only if DRAFT"""
        if not self.is_deletable:
            raise PermissionError("Only a draft invoice can be deleted.")
        self.lignes.all().delete()
        self.historique.filter(deleted_at__isnull=True).update(deleted_at=timezone.now())
        super().delete(*args, **kwargs)


# -------------------------------------------------------------------------
# INVOICE LINE
# -------------------------------------------------------------------------

class InvoiceLine(models.Model):
    """Invoice line (no soft delete, deleted with its parent)"""
    facture = models.ForeignKey(
        Invoice,
        on_delete=models.CASCADE,
        related_name='lignes',
        verbose_name='Facture',
    )
    ordre = models.IntegerField(default=0, verbose_name='Ordre')
    libelle = models.CharField(max_length=255, verbose_name='Libellé')
    description = models.TextField(blank=True, verbose_name='Description')
    quantite = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('1.00'),
        verbose_name='Quantité',
    )
    unite = models.CharField(max_length=20, blank=True, verbose_name='Unité')
    prix_unitaire_ht = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name='Prix unitaire HT',
    )
    taux_tva = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('20.00'),
        verbose_name='Taux TVA (%)',
    )
    montant_ht = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name='Montant HT',
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'lignes_factures'
        ordering = ['ordre', 'id']
        verbose_name = 'Ligne de facture'
        verbose_name_plural = 'Lignes de facture'

    def __str__(self):
        return f"{self.facture} - {self.libelle}"

    def save(self, *args, recalculate_totals=True, **kwargs):
        """Calculate the excl. tax amount and update invoice totals"""
        self.montant_ht = self.quantite * self.prix_unitaire_ht
        super().save(*args, **kwargs)
        if recalculate_totals:
            self.facture.calculate_totals()


# -------------------------------------------------------------------------
# INVOICE HISTORY
# -------------------------------------------------------------------------

class InvoiceHistory(SoftDeleteModel):
    """Status change history"""
    facture = models.ForeignKey(
        Invoice,
        on_delete=models.CASCADE,
        related_name='historique',
        verbose_name='Facture',
    )
    ancien_statut = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        verbose_name='Ancien statut',
    )
    nouveau_statut = models.CharField(max_length=20, verbose_name='Nouveau statut')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'historique_factures'
        ordering = ['-created_at']
        verbose_name = 'Historique de facture'
        verbose_name_plural = 'Historiques de facture'

    def __str__(self):
        if self.ancien_statut:
            return f"{self.facture} - {self.ancien_statut} → {self.nouveau_statut}"
        return f"{self.facture} - Creation"
