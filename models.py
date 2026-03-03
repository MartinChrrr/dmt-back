# """
# Modèles Django pour l'application de facturation MVP
# Basé sur le MCD v3 - 11 tables avec historique des statuts
# """

# from django.db import models
# from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
# from django.core.validators import MinValueValidator
# from decimal import Decimal


# # ==============================================
# # UTILISATEUR & CONFIGURATION
# # ==============================================

# class UtilisateurManager(BaseUserManager):
#     """Manager personnalisé pour le modèle Utilisateur."""
    
#     def create_user(self, email, password=None, **extra_fields):
#         if not email:
#             raise ValueError("L'adresse email est obligatoire")
#         email = self.normalize_email(email)
#         user = self.model(email=email, **extra_fields)
#         user.set_password(password)
#         user.save(using=self._db)
#         return user
    
#     def create_superuser(self, email, password=None, **extra_fields):
#         extra_fields.setdefault('is_staff', True)
#         extra_fields.setdefault('is_superuser', True)
#         return self.create_user(email, password, **extra_fields)


# class Utilisateur(AbstractBaseUser, PermissionsMixin):
#     """
#     Modèle utilisateur personnalisé.
#     Représente un entrepreneur/freelance utilisant l'application.
#     """
#     email = models.EmailField(unique=True, verbose_name="Email")
#     nom = models.CharField(max_length=100, verbose_name="Nom")
#     prenom = models.CharField(max_length=100, verbose_name="Prénom")
#     raison_sociale = models.CharField(max_length=255, blank=True, verbose_name="Raison sociale")
#     siret = models.CharField(max_length=14, blank=True, verbose_name="SIRET")
#     adresse = models.CharField(max_length=255, blank=True, verbose_name="Adresse")
#     code_postal = models.CharField(max_length=10, blank=True, verbose_name="Code postal")
#     ville = models.CharField(max_length=100, blank=True, verbose_name="Ville")
#     telephone = models.CharField(max_length=20, blank=True, verbose_name="Téléphone")
    
#     is_active = models.BooleanField(default=True)
#     is_staff = models.BooleanField(default=False)
    
#     created_at = models.DateTimeField(auto_now_add=True, verbose_name="Date de création")
#     updated_at = models.DateTimeField(auto_now=True, verbose_name="Date de modification")
    
#     objects = UtilisateurManager()
    
#     USERNAME_FIELD = 'email'
#     REQUIRED_FIELDS = ['nom', 'prenom']
    
#     class Meta:
#         verbose_name = "Utilisateur"
#         verbose_name_plural = "Utilisateurs"
#         ordering = ['nom', 'prenom']
    
#     def __str__(self):
#         return f"{self.prenom} {self.nom} ({self.email})"
    
#     @property
#     def nom_complet(self):
#         return f"{self.prenom} {self.nom}"


# class ConfigurationUtilisateur(models.Model):
#     """
#     Configuration personnalisée pour chaque utilisateur.
#     Gère les numéros de séquence et les préférences de facturation.
#     """
#     utilisateur = models.OneToOneField(
#         Utilisateur,
#         on_delete=models.CASCADE,
#         related_name='configuration',
#         verbose_name="Utilisateur"
#     )
#     prochain_numero_devis = models.PositiveIntegerField(
#         default=1,
#         verbose_name="Prochain numéro de devis"
#     )
#     prochain_numero_facture = models.PositiveIntegerField(
#         default=1,
#         verbose_name="Prochain numéro de facture"
#     )
#     prefixe_devis = models.CharField(
#         max_length=10,
#         default='DEV',
#         verbose_name="Préfixe devis"
#     )
#     prefixe_facture = models.CharField(
#         max_length=10,
#         default='FAC',
#         verbose_name="Préfixe facture"
#     )
#     delai_paiement_jours = models.PositiveIntegerField(
#         default=30,
#         verbose_name="Délai de paiement (jours)"
#     )
#     duree_validite_devis_jours = models.PositiveIntegerField(
#         default=30,
#         verbose_name="Durée de validité des devis (jours)"
#     )
    
#     created_at = models.DateTimeField(auto_now_add=True, verbose_name="Date de création")
#     updated_at = models.DateTimeField(auto_now=True, verbose_name="Date de modification")
    
#     class Meta:
#         verbose_name = "Configuration utilisateur"
#         verbose_name_plural = "Configurations utilisateurs"
    
#     def __str__(self):
#         return f"Configuration de {self.utilisateur}"


# # ==============================================
# # CLIENT & ADRESSE
# # ==============================================

# class Client(models.Model):
#     """
#     Client d'un utilisateur.
#     Peut être une entreprise ou un particulier.
#     """
#     utilisateur = models.ForeignKey(
#         Utilisateur,
#         on_delete=models.CASCADE,
#         related_name='clients',
#         verbose_name="Utilisateur"
#     )
#     raison_sociale = models.CharField(max_length=255, verbose_name="Raison sociale")
#     siret = models.CharField(max_length=14, blank=True, verbose_name="SIRET")
#     email = models.EmailField(blank=True, verbose_name="Email")
#     telephone = models.CharField(max_length=20, blank=True, verbose_name="Téléphone")
#     contact_nom = models.CharField(max_length=200, blank=True, verbose_name="Nom du contact")
#     contact_email = models.EmailField(blank=True, verbose_name="Email du contact")
#     contact_telephone = models.CharField(max_length=20, blank=True, verbose_name="Téléphone du contact")
#     notes = models.TextField(blank=True, verbose_name="Notes")
    
#     created_at = models.DateTimeField(auto_now_add=True, verbose_name="Date de création")
#     updated_at = models.DateTimeField(auto_now=True, verbose_name="Date de modification")
    
#     class Meta:
#         verbose_name = "Client"
#         verbose_name_plural = "Clients"
#         ordering = ['raison_sociale']
#         # Un client est unique par raison sociale pour un utilisateur donné
#         constraints = [
#             models.UniqueConstraint(
#                 fields=['utilisateur', 'raison_sociale'],
#                 name='unique_client_par_utilisateur'
#             )
#         ]
    
#     def __str__(self):
#         return self.raison_sociale


# class Adresse(models.Model):
#     """
#     Adresse associée à un client.
#     Un client peut avoir plusieurs adresses (siège, facturation, livraison).
#     """
#     class TypeAdresse(models.TextChoices):
#         SIEGE = 'SIEGE', 'Siège social'
#         FACTURATION = 'FACTURATION', 'Facturation'
#         LIVRAISON = 'LIVRAISON', 'Livraison'
    
#     client = models.ForeignKey(
#         Client,
#         on_delete=models.CASCADE,
#         related_name='adresses',
#         verbose_name="Client"
#     )
#     type = models.CharField(
#         max_length=20,
#         choices=TypeAdresse.choices,
#         default=TypeAdresse.SIEGE,
#         verbose_name="Type d'adresse"
#     )
#     ligne1 = models.CharField(max_length=255, verbose_name="Adresse ligne 1")
#     ligne2 = models.CharField(max_length=255, blank=True, verbose_name="Adresse ligne 2")
#     code_postal = models.CharField(max_length=10, verbose_name="Code postal")
#     ville = models.CharField(max_length=100, verbose_name="Ville")
#     pays = models.CharField(max_length=100, default='France', verbose_name="Pays")
    
#     created_at = models.DateTimeField(auto_now_add=True, verbose_name="Date de création")
#     updated_at = models.DateTimeField(auto_now=True, verbose_name="Date de modification")
    
#     class Meta:
#         verbose_name = "Adresse"
#         verbose_name_plural = "Adresses"
    
#     def __str__(self):
#         return f"{self.get_type_display()} - {self.ligne1}, {self.code_postal} {self.ville}"
    
#     @property
#     def adresse_complete(self):
#         lignes = [self.ligne1]
#         if self.ligne2:
#             lignes.append(self.ligne2)
#         lignes.append(f"{self.code_postal} {self.ville}")
#         if self.pays != 'France':
#             lignes.append(self.pays)
#         return '\n'.join(lignes)


# # ==============================================
# # CATALOGUE (PRESTATIONS)
# # ==============================================

# class Prestation(models.Model):
#     """
#     Prestation du catalogue d'un utilisateur.
#     Permet de créer rapidement des lignes de devis/facture.
#     """
#     class Unite(models.TextChoices):
#         HEURE = 'heure', 'Heure'
#         JOUR = 'jour', 'Jour'
#         FORFAIT = 'forfait', 'Forfait'
#         UNITE = 'unité', 'Unité'
    
#     class TauxTVA(models.TextChoices):
#         TVA_20 = '20.00', '20%'
#         TVA_10 = '10.00', '10%'
#         TVA_5_5 = '5.50', '5.5%'
#         TVA_0 = '0.00', '0%'
    
#     utilisateur = models.ForeignKey(
#         Utilisateur,
#         on_delete=models.CASCADE,
#         related_name='prestations',
#         verbose_name="Utilisateur"
#     )
#     libelle = models.CharField(max_length=255, verbose_name="Libellé")
#     description = models.TextField(blank=True, verbose_name="Description")
#     prix_unitaire_ht = models.DecimalField(
#         max_digits=10,
#         decimal_places=2,
#         validators=[MinValueValidator(Decimal('0.00'))],
#         verbose_name="Prix unitaire HT"
#     )
#     unite = models.CharField(
#         max_length=20,
#         choices=Unite.choices,
#         default=Unite.HEURE,
#         verbose_name="Unité"
#     )
#     taux_tva = models.DecimalField(
#         max_digits=5,
#         decimal_places=2,
#         choices=[(Decimal(c[0]), c[1]) for c in TauxTVA.choices],
#         default=Decimal('20.00'),
#         verbose_name="Taux de TVA"
#     )
    
#     created_at = models.DateTimeField(auto_now_add=True, verbose_name="Date de création")
#     updated_at = models.DateTimeField(auto_now=True, verbose_name="Date de modification")
    
#     class Meta:
#         verbose_name = "Prestation"
#         verbose_name_plural = "Prestations"
#         ordering = ['libelle']
    
#     def __str__(self):
#         return f"{self.libelle} - {self.prix_unitaire_ht}€ HT/{self.unite}"


# # ==============================================
# # DEVIS
# # ==============================================

# class Devis(models.Model):
#     """
#     Devis émis par un utilisateur pour un client.
#     """
#     class Statut(models.TextChoices):
#         BROUILLON = 'BROUILLON', 'Brouillon'
#         ENVOYE = 'ENVOYE', 'Envoyé'
#         ACCEPTE = 'ACCEPTE', 'Accepté'
#         REFUSE = 'REFUSE', 'Refusé'
#         EXPIRE = 'EXPIRE', 'Expiré'
    
#     utilisateur = models.ForeignKey(
#         Utilisateur,
#         on_delete=models.CASCADE,
#         related_name='devis',
#         verbose_name="Utilisateur"
#     )
#     client = models.ForeignKey(
#         Client,
#         on_delete=models.PROTECT,
#         related_name='devis',
#         verbose_name="Client"
#     )
#     numero = models.CharField(
#         max_length=50,
#         unique=True,
#         verbose_name="Numéro de devis"
#     )
#     date_emission = models.DateField(verbose_name="Date d'émission")
#     date_validite = models.DateField(verbose_name="Date de validité")
#     statut = models.CharField(
#         max_length=20,
#         choices=Statut.choices,
#         default=Statut.BROUILLON,
#         verbose_name="Statut"
#     )
#     objet = models.CharField(max_length=255, verbose_name="Objet")
#     notes = models.TextField(blank=True, verbose_name="Notes")
#     total_ht = models.DecimalField(
#         max_digits=12,
#         decimal_places=2,
#         default=Decimal('0.00'),
#         verbose_name="Total HT"
#     )
#     total_tva = models.DecimalField(
#         max_digits=12,
#         decimal_places=2,
#         default=Decimal('0.00'),
#         verbose_name="Total TVA"
#     )
#     total_ttc = models.DecimalField(
#         max_digits=12,
#         decimal_places=2,
#         default=Decimal('0.00'),
#         verbose_name="Total TTC"
#     )
    
#     created_at = models.DateTimeField(auto_now_add=True, verbose_name="Date de création")
#     updated_at = models.DateTimeField(auto_now=True, verbose_name="Date de modification")
    
#     class Meta:
#         verbose_name = "Devis"
#         verbose_name_plural = "Devis"
#         ordering = ['-date_emission', '-numero']
    
#     def __str__(self):
#         return f"{self.numero} - {self.client.raison_sociale}"
    
#     def calculer_totaux(self):
#         """Recalcule les totaux à partir des lignes."""
#         lignes = self.lignes.all()
#         self.total_ht = sum(ligne.montant_ht for ligne in lignes)
#         self.total_tva = sum(
#             ligne.montant_ht * ligne.taux_tva / Decimal('100')
#             for ligne in lignes
#         )
#         self.total_ttc = self.total_ht + self.total_tva
    
#     def changer_statut(self, nouveau_statut):
#         """Change le statut et crée une entrée d'historique."""
#         ancien_statut = self.statut
#         self.statut = nouveau_statut
#         self.save()
#         HistoriqueDevis.objects.create(
#             devis=self,
#             ancien_statut=ancien_statut,
#             nouveau_statut=nouveau_statut
#         )


# class LigneDevis(models.Model):
#     """
#     Ligne d'un devis.
#     """
#     devis = models.ForeignKey(
#         Devis,
#         on_delete=models.CASCADE,
#         related_name='lignes',
#         verbose_name="Devis"
#     )
#     ordre = models.PositiveIntegerField(default=0, verbose_name="Ordre")
#     libelle = models.CharField(max_length=255, verbose_name="Libellé")
#     description = models.TextField(blank=True, verbose_name="Description")
#     quantite = models.DecimalField(
#         max_digits=10,
#         decimal_places=2,
#         validators=[MinValueValidator(Decimal('0.01'))],
#         verbose_name="Quantité"
#     )
#     unite = models.CharField(max_length=20, verbose_name="Unité")
#     prix_unitaire_ht = models.DecimalField(
#         max_digits=10,
#         decimal_places=2,
#         validators=[MinValueValidator(Decimal('0.00'))],
#         verbose_name="Prix unitaire HT"
#     )
#     taux_tva = models.DecimalField(
#         max_digits=5,
#         decimal_places=2,
#         default=Decimal('20.00'),
#         verbose_name="Taux de TVA"
#     )
#     montant_ht = models.DecimalField(
#         max_digits=12,
#         decimal_places=2,
#         verbose_name="Montant HT"
#     )
    
#     created_at = models.DateTimeField(auto_now_add=True, verbose_name="Date de création")
    
#     class Meta:
#         verbose_name = "Ligne de devis"
#         verbose_name_plural = "Lignes de devis"
#         ordering = ['ordre']
    
#     def __str__(self):
#         return f"{self.libelle} - {self.montant_ht}€ HT"
    
#     def save(self, *args, **kwargs):
#         """Calcule automatiquement le montant HT avant sauvegarde."""
#         self.montant_ht = self.quantite * self.prix_unitaire_ht
#         super().save(*args, **kwargs)


# class HistoriqueDevis(models.Model):
#     """
#     Historique des changements de statut d'un devis.
#     """
#     devis = models.ForeignKey(
#         Devis,
#         on_delete=models.CASCADE,
#         related_name='historique',
#         verbose_name="Devis"
#     )
#     ancien_statut = models.CharField(
#         max_length=20,
#         choices=Devis.Statut.choices,
#         null=True,
#         blank=True,
#         verbose_name="Ancien statut"
#     )
#     nouveau_statut = models.CharField(
#         max_length=20,
#         choices=Devis.Statut.choices,
#         verbose_name="Nouveau statut"
#     )
    
#     created_at = models.DateTimeField(auto_now_add=True, verbose_name="Date")
    
#     class Meta:
#         verbose_name = "Historique de devis"
#         verbose_name_plural = "Historiques de devis"
#         ordering = ['-created_at']
    
#     def __str__(self):
#         if self.ancien_statut:
#             return f"{self.devis.numero}: {self.ancien_statut} → {self.nouveau_statut}"
#         return f"{self.devis.numero}: Création ({self.nouveau_statut})"


# # ==============================================
# # FACTURE
# # ==============================================

# class Facture(models.Model):
#     """
#     Facture émise par un utilisateur pour un client.
#     Peut être créée à partir d'un devis accepté.
#     """
#     class Statut(models.TextChoices):
#         BROUILLON = 'BROUILLON', 'Brouillon'
#         ENVOYEE = 'ENVOYEE', 'Envoyée'
#         PAYEE = 'PAYEE', 'Payée'
#         EN_RETARD = 'EN_RETARD', 'En retard'
    
#     utilisateur = models.ForeignKey(
#         Utilisateur,
#         on_delete=models.CASCADE,
#         related_name='factures',
#         verbose_name="Utilisateur"
#     )
#     client = models.ForeignKey(
#         Client,
#         on_delete=models.PROTECT,
#         related_name='factures',
#         verbose_name="Client"
#     )
#     devis_origine = models.ForeignKey(
#         Devis,
#         on_delete=models.SET_NULL,
#         null=True,
#         blank=True,
#         related_name='factures',
#         verbose_name="Devis d'origine"
#     )
#     numero = models.CharField(
#         max_length=50,
#         unique=True,
#         verbose_name="Numéro de facture"
#     )
#     date_emission = models.DateField(verbose_name="Date d'émission")
#     date_echeance = models.DateField(verbose_name="Date d'échéance")
#     statut = models.CharField(
#         max_length=20,
#         choices=Statut.choices,
#         default=Statut.BROUILLON,
#         verbose_name="Statut"
#     )
#     objet = models.CharField(max_length=255, verbose_name="Objet")
#     notes = models.TextField(blank=True, verbose_name="Notes")
#     total_ht = models.DecimalField(
#         max_digits=12,
#         decimal_places=2,
#         default=Decimal('0.00'),
#         verbose_name="Total HT"
#     )
#     total_tva = models.DecimalField(
#         max_digits=12,
#         decimal_places=2,
#         default=Decimal('0.00'),
#         verbose_name="Total TVA"
#     )
#     total_ttc = models.DecimalField(
#         max_digits=12,
#         decimal_places=2,
#         default=Decimal('0.00'),
#         verbose_name="Total TTC"
#     )
    
#     created_at = models.DateTimeField(auto_now_add=True, verbose_name="Date de création")
#     updated_at = models.DateTimeField(auto_now=True, verbose_name="Date de modification")
    
#     class Meta:
#         verbose_name = "Facture"
#         verbose_name_plural = "Factures"
#         ordering = ['-date_emission', '-numero']
    
#     def __str__(self):
#         return f"{self.numero} - {self.client.raison_sociale}"
    
#     def calculer_totaux(self):
#         """Recalcule les totaux à partir des lignes."""
#         lignes = self.lignes.all()
#         self.total_ht = sum(ligne.montant_ht for ligne in lignes)
#         self.total_tva = sum(
#             ligne.montant_ht * ligne.taux_tva / Decimal('100')
#             for ligne in lignes
#         )
#         self.total_ttc = self.total_ht + self.total_tva
    
#     def changer_statut(self, nouveau_statut):
#         """Change le statut et crée une entrée d'historique."""
#         ancien_statut = self.statut
#         self.statut = nouveau_statut
#         self.save()
#         HistoriqueFacture.objects.create(
#             facture=self,
#             ancien_statut=ancien_statut,
#             nouveau_statut=nouveau_statut
#         )
    
#     @classmethod
#     def creer_depuis_devis(cls, devis):
#         """Crée une facture à partir d'un devis accepté."""
#         if devis.statut != Devis.Statut.ACCEPTE:
#             raise ValueError("Le devis doit être accepté pour créer une facture")
        
#         facture = cls(
#             utilisateur=devis.utilisateur,
#             client=devis.client,
#             devis_origine=devis,
#             objet=devis.objet,
#             notes=devis.notes,
#             total_ht=devis.total_ht,
#             total_tva=devis.total_tva,
#             total_ttc=devis.total_ttc,
#         )
#         return facture


# class LigneFacture(models.Model):
#     """
#     Ligne d'une facture.
#     """
#     facture = models.ForeignKey(
#         Facture,
#         on_delete=models.CASCADE,
#         related_name='lignes',
#         verbose_name="Facture"
#     )
#     ordre = models.PositiveIntegerField(default=0, verbose_name="Ordre")
#     libelle = models.CharField(max_length=255, verbose_name="Libellé")
#     description = models.TextField(blank=True, verbose_name="Description")
#     quantite = models.DecimalField(
#         max_digits=10,
#         decimal_places=2,
#         validators=[MinValueValidator(Decimal('0.01'))],
#         verbose_name="Quantité"
#     )
#     unite = models.CharField(max_length=20, verbose_name="Unité")
#     prix_unitaire_ht = models.DecimalField(
#         max_digits=10,
#         decimal_places=2,
#         validators=[MinValueValidator(Decimal('0.00'))],
#         verbose_name="Prix unitaire HT"
#     )
#     taux_tva = models.DecimalField(
#         max_digits=5,
#         decimal_places=2,
#         default=Decimal('20.00'),
#         verbose_name="Taux de TVA"
#     )
#     montant_ht = models.DecimalField(
#         max_digits=12,
#         decimal_places=2,
#         verbose_name="Montant HT"
#     )
    
#     created_at = models.DateTimeField(auto_now_add=True, verbose_name="Date de création")
    
#     class Meta:
#         verbose_name = "Ligne de facture"
#         verbose_name_plural = "Lignes de facture"
#         ordering = ['ordre']
    
#     def __str__(self):
#         return f"{self.libelle} - {self.montant_ht}€ HT"
    
#     def save(self, *args, **kwargs):
#         """Calcule automatiquement le montant HT avant sauvegarde."""
#         self.montant_ht = self.quantite * self.prix_unitaire_ht
#         super().save(*args, **kwargs)


# class HistoriqueFacture(models.Model):
#     """
#     Historique des changements de statut d'une facture.
#     """
#     facture = models.ForeignKey(
#         Facture,
#         on_delete=models.CASCADE,
#         related_name='historique',
#         verbose_name="Facture"
#     )
#     ancien_statut = models.CharField(
#         max_length=20,
#         choices=Facture.Statut.choices,
#         null=True,
#         blank=True,
#         verbose_name="Ancien statut"
#     )
#     nouveau_statut = models.CharField(
#         max_length=20,
#         choices=Facture.Statut.choices,
#         verbose_name="Nouveau statut"
#     )
    
#     created_at = models.DateTimeField(auto_now_add=True, verbose_name="Date")
    
#     class Meta:
#         verbose_name = "Historique de facture"
#         verbose_name_plural = "Historiques de facture"
#         ordering = ['-created_at']
    
#     def __str__(self):
#         if self.ancien_statut:
#             return f"{self.facture.numero}: {self.ancien_statut} → {self.nouveau_statut}"
#         return f"{self.facture.numero}: Création ({self.nouveau_statut})"
