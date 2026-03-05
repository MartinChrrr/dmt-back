from django.db import models
from django.conf import settings

class Client(models.Model):
    """
    Client d'un utilisateur.
    Peut être une entreprise ou un particulier.
    """
    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='clients',
        verbose_name="Utilisateur"
    )
    raison_sociale = models.CharField(max_length=255, verbose_name="Raison sociale")
    siret = models.CharField(max_length=14, blank=True, verbose_name="SIRET")
    email = models.EmailField(blank=True, verbose_name="Email")
    telephone = models.CharField(max_length=20, blank=True, verbose_name="Téléphone")
    contact_nom = models.CharField(max_length=200, blank=True, verbose_name="Nom du contact")
    contact_email = models.EmailField(blank=True, verbose_name="Email du contact")
    contact_telephone = models.CharField(max_length=20, blank=True, verbose_name="Téléphone du contact")
    notes = models.TextField(blank=True, verbose_name="Notes")

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Date de création")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Date de modification")

    class Meta:
        db_table = 'clients_client'
        verbose_name = "Client"
        verbose_name_plural = "Clients"
        ordering = ['raison_sociale']
        constraints = [
            models.UniqueConstraint(
                fields=['utilisateur', 'raison_sociale'],
                name='unique_client_par_utilisateur'
            )
        ]

    def __str__(self):
        return self.raison_sociale


class Adresse(models.Model):
    """
    Adresse associée à un client.
    Un client peut avoir plusieurs adresses (siège, facturation, livraison).
    """
    class TypeAdresse(models.TextChoices):
        SIEGE = 'SIEGE', 'Siège social'
        FACTURATION = 'FACTURATION', 'Facturation'
        LIVRAISON = 'LIVRAISON', 'Livraison'

    client = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        related_name='adresses',
        verbose_name="Client"
    )
    type = models.CharField(
        max_length=20,
        choices=TypeAdresse.choices,
        default=TypeAdresse.SIEGE,
        verbose_name="Type d'adresse"
    )
    ligne1 = models.CharField(max_length=255, verbose_name="Adresse ligne 1")
    ligne2 = models.CharField(max_length=255, blank=True, verbose_name="Adresse ligne 2")
    code_postal = models.CharField(max_length=10, verbose_name="Code postal")
    ville = models.CharField(max_length=100, verbose_name="Ville")
    pays = models.CharField(max_length=100, default='France', verbose_name="Pays")

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Date de création")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Date de modification")

    class Meta:
        verbose_name = "Adresse"
        verbose_name_plural = "Adresses"
        ordering =['id']
        
    def __str__(self):
        return f"{self.get_type_display()} - {self.ligne1}, {self.code_postal} {self.ville}"

    @property
    def adresse_complete(self):
        lignes = [self.ligne1]
        if self.ligne2:
            lignes.append(self.ligne2)
        lignes.append(f"{self.code_postal} {self.ville}")
        if self.pays != 'France':
            lignes.append(self.pays)
        return '\n'.join(lignes)
