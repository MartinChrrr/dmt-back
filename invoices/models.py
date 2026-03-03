from datetime import date
from django.conf import settings
from django.db import models
from django.utils import timezone
from decimal import Decimal


# -------------------------------------------------------------------------
# SOFT DELETE (réutilisable — à terme, mutualiser dans un module commun)
# -------------------------------------------------------------------------

class SoftDeleteManager(models.Manager):
    """Manager qui exclut automatiquement les objets supprimés"""
    def get_queryset(self):
        return super().get_queryset().filter(deleted_at__isnull=True)


class SoftDeleteModel(models.Model):
    """Modèle abstrait pour le soft delete"""
    deleted_at = models.DateTimeField(null=True, blank=True, verbose_name="Date de suppression")

    objects = SoftDeleteManager()
    all_objects = models.Manager()

    class Meta:
        abstract = True

    def delete(self, *args, **kwargs):
        """Soft delete : marque comme supprimé"""
        self.deleted_at = timezone.now()
        self.save(update_fields=['deleted_at'])


# -------------------------------------------------------------------------
# FACTURE
# -------------------------------------------------------------------------

class Facture(SoftDeleteModel):
    """Facture émise par l'utilisateur"""
    STATUT_BROUILLON = 'BROUILLON'
    STATUT_ENVOYEE = 'ENVOYEE'
    STATUT_PAYEE = 'PAYEE'
    STATUT_EN_RETARD = 'EN_RETARD'

    STATUT_CHOICES = [
        (STATUT_BROUILLON, 'Brouillon'),
        (STATUT_ENVOYEE, 'Envoyée'),
        (STATUT_PAYEE, 'Payée'),
        (STATUT_EN_RETARD, 'En retard'),
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
        'quotes.Devis',
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
        return self.numero or f"Brouillon #{self.pk}"

    @property
    def est_modifiable(self):
        return self.statut == self.STATUT_BROUILLON

    @property
    def est_supprimable(self):
        return self.statut == self.STATUT_BROUILLON

    def calculer_totaux(self):
        """Calcule les totaux HT, TVA et TTC à partir des lignes"""
        lignes = list(self.lignes.all())

        self.total_ht = sum((ligne.montant_ht for ligne in lignes), Decimal('0.00'))
        self.total_tva = sum(
            (ligne.montant_ht * ligne.taux_tva / Decimal('100') for ligne in lignes),
            Decimal('0.00'),
        )
        self.total_ttc = self.total_ht + self.total_tva
        self.save(update_fields=['total_ht', 'total_tva', 'total_ttc'])

    def delete(self, *args, **kwargs):
        """Soft delete — uniquement si BROUILLON"""
        if not self.est_supprimable:
            raise PermissionError("Seule une facture en brouillon peut être supprimée.")
        self.lignes.all().delete()
        self.historique.filter(deleted_at__isnull=True).update(deleted_at=timezone.now())
        super().delete(*args, **kwargs)


# -------------------------------------------------------------------------
# LIGNE FACTURE
# -------------------------------------------------------------------------

class LigneFacture(models.Model):
    """Ligne d'une facture (pas de soft delete, supprimée avec son parent)"""
    facture = models.ForeignKey(
        Facture,
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

    def save(self, *args, recalculer_totaux=True, **kwargs):
        """Calcule le montant HT et met à jour les totaux de la facture"""
        self.montant_ht = self.quantite * self.prix_unitaire_ht
        super().save(*args, **kwargs)
        if recalculer_totaux:
            self.facture.calculer_totaux()


# -------------------------------------------------------------------------
# HISTORIQUE FACTURE
# -------------------------------------------------------------------------

class HistoriqueFacture(SoftDeleteModel):
    """Historique des changements de statut"""
    facture = models.ForeignKey(
        Facture,
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
        return f"{self.facture} - Création"