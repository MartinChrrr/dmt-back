from django.db import models

# Create your models here.
from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Modèle utilisateur personnalisé"""
    # On garde les champs de base de Django (username, password, etc.)
    # Et on ajoute nos propres champs
    
    email = models.EmailField(unique=True, verbose_name="Email")
    company_name = models.CharField(max_length=255, blank=True, verbose_name="Nom de l'entreprise")
    siret = models.CharField(max_length=14, blank=True, verbose_name="SIRET")
    address = models.CharField(max_length=255, blank=True, verbose_name="Adresse")
    postal_code = models.CharField(max_length=10, blank=True, verbose_name="Code postal")
    city = models.CharField(max_length=100, blank=True, verbose_name="Ville")
    phone = models.CharField(max_length=20, blank=True, verbose_name="Téléphone")

    # On dit à Django d'utiliser l'email pour se connecter au lieu du username
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']  # Champs demandés lors de createsuperuser

    class Meta:
        verbose_name = "Utilisateur"
        verbose_name_plural = "Utilisateurs"

    def __str__(self):
        return self.email


class UserConfiguration(models.Model):
    """Configuration pour la numérotation des devis et factures"""
    
    # Lien avec l'utilisateur (OneToOne = 1 config par utilisateur)
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,  # Si on supprime l'user, on supprime sa config
        related_name='configuration'
    )
    
    # Numérotation
    next_quote_number = models.IntegerField(default=1, verbose_name="Prochain numéro de devis")
    next_invoice_number = models.IntegerField(default=1, verbose_name="Prochain numéro de facture")
    
    # Préfixes
    quote_prefix = models.CharField(max_length=10, default="DEV", verbose_name="Préfixe devis")
    invoice_prefix = models.CharField(max_length=10, default="FAC", verbose_name="Préfixe facture")
    
    # Délais par défaut
    payment_deadline_days = models.IntegerField(default=30, verbose_name="Délai de paiement (jours)")
    quote_validity_days = models.IntegerField(default=30, verbose_name="Validité du devis (jours)")
    
    # Dates
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Configuration utilisateur"
        verbose_name_plural = "Configurations utilisateurs"

    def __str__(self):
        return f"Configuration de {self.user.email}"