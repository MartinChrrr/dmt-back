from django.db import models
from django.utils import timezone
from decimal import Decimal
from django.conf import settings


# SOFT DELETE

class SoftDeleteManager(models.Manager):
    # Manager qui exclut automatiquement les objets supprimés
    def get_queryset(self):
        return super().get_queryset().filter(deleted_at__isnull=True)


class SoftDeleteModel(models.Model):
    # Modèle abstrait pour le soft delete
    deleted_at = models.DateTimeField(null=True, blank=True, verbose_name="Date de suppression")
    
    objects = SoftDeleteManager()
    all_objects = models.Manager()
    
    class Meta:
        abstract = True
    
    def delete(self, *args, **kwargs):
        # Soft delete : marque comme supprimé
        self.deleted_at = timezone.now()
        self.save()


# DEVIS

class Devis(SoftDeleteModel):
    # Devis émis par l'utilisateur
    STATUT_BROUILLON = 'BROUILLON'
    STATUT_ENVOYE = 'ENVOYE'
    STATUT_ACCEPTE = 'ACCEPTE'
    STATUT_REFUSE = 'REFUSE'
    STATUT_EXPIRE = 'EXPIRE'
    
    STATUT_CHOICES = [
        (STATUT_BROUILLON, 'Brouillon'),
        (STATUT_ENVOYE, 'Envoyé'),
        (STATUT_ACCEPTE, 'Accepté'),
        (STATUT_REFUSE, 'Refusé'),
        (STATUT_EXPIRE, 'Expiré'),
    ]
    
    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='devis',
        verbose_name='Utilisateur'
    )
    client = models.ForeignKey(
        'clients.Client',  # Référence au modèle Client
        on_delete=models.PROTECT,  # Empêche de supprimer un client avec des devis
        related_name='devis',
        verbose_name='Client'
    )
    numero = models.CharField(max_length=50, unique=True, blank=True, verbose_name='Numéro')
    date_emission = models.DateField(default=timezone.now, verbose_name='Date d\'émission')
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
    def est_modifiable(self):
        return self.statut == self.STATUT_BROUILLON

    @property
    def est_supprimable(self):
        return self.statut == self.STATUT_BROUILLON

    def save(self, *args, **kwargs):
        # Génère automatiquement le numéro si vide
        if not self.numero:
            self.numero = self._generer_numero()
        super().save(*args, **kwargs)

    def _generer_numero(self):
        from datetime import datetime
        from accounts.models import UserConfiguration

        config, _ = UserConfiguration.objects.get_or_create(user=self.utilisateur)
        prefix = config.quote_prefix
        annee = datetime.now().year
        numero = f"{prefix}-{annee}-{config.next_quote_number:03d}"
        config.next_quote_number += 1
        config.save()
        return numero

    
    def calculer_totaux(self):
        # Calcule les totaux HT, TVA et TTC
        lignes = self.lignes.filter(deleted_at__isnull=True)
        
        self.total_ht = sum(ligne.montant_ht for ligne in lignes) or Decimal('0.00')
        self.total_tva = sum(ligne.montant_ht * (ligne.taux_tva / 100) for ligne in lignes) or Decimal('0.00')
        self.total_ttc = self.total_ht + self.total_tva
        self.save()
    
    def delete(self, *args, **kwargs):
        if not self.est_supprimable:
            raise ValueError("Impossible de supprimer un devis qui n'est pas en brouillon.")
        # Soft delete en cascade
        for ligne in self.lignes.all():
            ligne.delete()
        for historique in self.historique.all():
            historique.delete()
        super().delete(*args, **kwargs)


class LigneDevis(SoftDeleteModel):
    # Ligne d'un devis
    devis = models.ForeignKey(
        Devis,
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
        # Calcule le montant HT et met à jour les totaux du devis
        self.montant_ht = self.quantite * self.prix_unitaire_ht
        super().save(*args, **kwargs)
        self.devis.calculer_totaux()
    
    def delete(self, *args, **kwargs):
        # Soft delete et recalcul des totaux
        devis = self.devis
        super().delete(*args, **kwargs)
        devis.calculer_totaux()


class HistoriqueDevis(SoftDeleteModel):
    # Historique des changements de statut
    devis = models.ForeignKey(
        Devis,
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
        return f"{self.devis.numero} - Création"