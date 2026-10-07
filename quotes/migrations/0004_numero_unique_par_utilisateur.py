# Generated manually — fix: numero unique global → unique par utilisateur

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('quotes', '0003_alter_quote_date_emission_alter_quote_statut'),
    ]

    operations = [
        migrations.AlterField(
            model_name='quote',
            name='numero',
            field=models.CharField(blank=True, max_length=50, verbose_name='Numéro'),
        ),
        migrations.AddConstraint(
            model_name='quote',
            constraint=models.UniqueConstraint(
                fields=('utilisateur', 'numero'),
                name='unique_numero_devis_par_utilisateur',
            ),
        ),
    ]
