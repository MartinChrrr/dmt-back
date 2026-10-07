# Generated manually — fix: numero unique global → unique par utilisateur

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('invoices', '0003_alter_invoice_statut'),
    ]

    operations = [
        migrations.AlterField(
            model_name='invoice',
            name='numero',
            field=models.CharField(blank=True, max_length=50, null=True, verbose_name='Numéro'),
        ),
        migrations.AddConstraint(
            model_name='invoice',
            constraint=models.UniqueConstraint(
                fields=('utilisateur', 'numero'),
                name='unique_numero_facture_par_utilisateur',
            ),
        ),
    ]
