from django.db import models
from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Custom user model"""
    # Keep Django's base fields (username, password, etc.)
    # And add our own fields

    email = models.EmailField(unique=True, verbose_name="Email")
    company_name = models.CharField(max_length=255, blank=True, verbose_name="Nom de l'entreprise")
    siret = models.CharField(max_length=14, blank=True, verbose_name="SIRET")
    address = models.CharField(max_length=255, blank=True, verbose_name="Adresse")
    postal_code = models.CharField(max_length=10, blank=True, verbose_name="Code postal")
    city = models.CharField(max_length=100, blank=True, verbose_name="Ville")
    phone = models.CharField(max_length=20, blank=True, verbose_name="Téléphone")

    # Use email to log in instead of username
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']  # Fields required during createsuperuser

    class Meta:
        verbose_name = "Utilisateur"
        verbose_name_plural = "Utilisateurs"

    def __str__(self):
        return self.email


class UserConfiguration(models.Model):
    """Configuration for quote and invoice numbering"""

    # Link to user (OneToOne = 1 config per user)
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,  # If user is deleted, delete their config
        related_name='configuration'
    )

    # Numbering
    next_quote_number = models.IntegerField(default=1, verbose_name="Prochain numéro de devis")
    next_invoice_number = models.IntegerField(default=1, verbose_name="Prochain numéro de facture")

    # Prefixes
    quote_prefix = models.CharField(max_length=10, default="DEV", verbose_name="Préfixe devis")
    invoice_prefix = models.CharField(max_length=10, default="FAC", verbose_name="Préfixe facture")

    # Default deadlines
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
