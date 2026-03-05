from decimal import Decimal
from django.conf import settings
from django.db import models


class Service(models.Model):

    UNITS = [
        ("heure", "Hour"),
        ("jour", "Day"),
        ("forfait", "Flat rate"),
    ]

    VAT = [
        (Decimal("20.00"), "20%"),
        (Decimal("10.00"), "10%"),
        (Decimal("5.50"), "5.5%"),
        (Decimal("0.00"), "0%"),
    ]

    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="prestations",
        verbose_name="Utilisateur",
    )

    label = models.CharField(max_length=255, verbose_name="Libellé")
    description = models.TextField(blank=True, verbose_name="Description")
    unit_price_excl_tax = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Prix unitaire HT")
    unit = models.CharField(max_length=20, choices=UNITS, verbose_name="Unité")
    taux_tva = models.DecimalField(max_digits=4, choices=VAT, decimal_places=2, verbose_name="Taux TVA")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'services_prestation'
        verbose_name = "Service"
        verbose_name_plural = "Services"

    def __str__(self):
        return self.label
