import csv
import io
import zipfile
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import UserConfiguration
from clients.models import Address, Client
from invoices.models import Invoice, InvoiceLine
from quotes.models import Quote, QuoteLine
from services.models import Service

User = get_user_model()


def _create_user(email, *, is_staff=False, is_superuser=False, **extra):
    """Helper: create a user + their UserConfiguration."""
    user = User.objects.create_user(
        username=email.split('@')[0],
        email=email,
        password='Testpass123!',
        is_staff=is_staff,
        is_superuser=is_superuser,
        **extra,
    )
    UserConfiguration.objects.create(user=user)
    return user


def _seed_user_data(user):
    """Create one full set of business records owned by `user`."""
    client = Client.objects.create(
        utilisateur=user,
        raison_sociale=f"ACME for {user.email}",
        siret="12345678901234",
        email="contact@acme.test",
    )
    Address.objects.create(
        client=client,
        type=Address.AddressType.SIEGE,
        ligne1="1 rue du Test",
        code_postal="75001",
        ville="Paris",
    )
    service = Service.objects.create(
        utilisateur=user,
        label="Dév web",
        unit_price_excl_tax=Decimal("500.00"),
        unit="jour",
        taux_tva=Decimal("20.00"),
    )
    quote = Quote.objects.create(utilisateur=user, client=client, objet="Site vitrine")
    QuoteLine.objects.create(
        devis=quote,
        ordre=1,
        libelle="Prestation",
        quantite=Decimal("2.00"),
        prix_unitaire_ht=Decimal("500.00"),
        taux_tva=Decimal("20.00"),
    )
    invoice = Invoice.objects.create(
        utilisateur=user,
        client=client,
        numero="FAC-TEST-001",
        date_echeance=date.today() + timedelta(days=30),
    )
    InvoiceLine.objects.create(
        facture=invoice,
        ordre=1,
        libelle="Prestation",
        quantite=Decimal("1.00"),
        prix_unitaire_ht=Decimal("300.00"),
        taux_tva=Decimal("20.00"),
    )
    return {
        "client": client,
        "service": service,
        "quote": quote,
        "invoice": invoice,
    }


class AdminUserListTests(TestCase):
    """GET /api/admin/users/"""

    def setUp(self):
        self.api_client = APIClient()
        self.url = '/api/admin/users/'
        self.admin = _create_user('admin@test.com', is_staff=True)
        self.standard = _create_user('user@test.com')
        _seed_user_data(self.standard)

    def test_admin_lists_all_users(self):
        self.api_client.force_authenticate(user=self.admin)
        response = self.api_client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'success')
        emails = {u['email'] for u in response.data['data']}
        self.assertIn('admin@test.com', emails)
        self.assertIn('user@test.com', emails)

    def test_counts_are_annotated(self):
        self.api_client.force_authenticate(user=self.admin)
        response = self.api_client.get(self.url)

        seeded = next(u for u in response.data['data'] if u['email'] == 'user@test.com')
        self.assertEqual(seeded['clients_count'], 1)
        self.assertEqual(seeded['quotes_count'], 1)
        self.assertEqual(seeded['invoices_count'], 1)

    def test_non_admin_forbidden(self):
        self.api_client.force_authenticate(user=self.standard)
        response = self.api_client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data['status'], 'fail')

    def test_unauthenticated_unauthorized(self):
        response = self.api_client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data['status'], 'fail')


class AdminUserDeleteTests(TestCase):
    """DELETE /api/admin/users/<id>/"""

    def setUp(self):
        self.api_client = APIClient()
        self.admin = _create_user('admin@test.com', is_staff=True)
        self.target = _create_user('target@test.com')
        self.seeded = _seed_user_data(self.target)
        self.url = f'/api/admin/users/{self.target.pk}/'

    def test_admin_deletes_user_and_cascades(self):
        self.api_client.force_authenticate(user=self.admin)
        response = self.api_client.delete(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'success')
        self.assertFalse(User.objects.filter(pk=self.target.pk).exists())
        # Cascade vérifié sur toutes les entités métier
        self.assertFalse(Client.objects.filter(utilisateur_id=self.target.pk).exists())
        self.assertFalse(Service.objects.filter(utilisateur_id=self.target.pk).exists())
        self.assertFalse(Quote.all_objects.filter(utilisateur_id=self.target.pk).exists())
        self.assertFalse(QuoteLine.all_objects.filter(devis__utilisateur_id=self.target.pk).exists())
        self.assertFalse(Invoice.all_objects.filter(utilisateur_id=self.target.pk).exists())
        self.assertFalse(InvoiceLine.objects.filter(facture__utilisateur_id=self.target.pk).exists())
        self.assertFalse(Address.objects.filter(client__utilisateur_id=self.target.pk).exists())

    def test_soft_deleted_quotes_are_purged(self):
        """Les devis déjà soft-deleted doivent aussi être effacés (RGPD)."""
        # Soft-delete d'un devis avant l'opération
        self.seeded['quote'].deleted_at = self.seeded['quote'].created_at
        self.seeded['quote'].save(update_fields=['deleted_at'])

        self.api_client.force_authenticate(user=self.admin)
        self.api_client.delete(self.url)

        self.assertFalse(Quote.all_objects.filter(utilisateur_id=self.target.pk).exists())

    def test_cannot_delete_superuser(self):
        super_user = _create_user('super@test.com', is_staff=True, is_superuser=True)
        self.api_client.force_authenticate(user=self.admin)
        response = self.api_client.delete(f'/api/admin/users/{super_user.pk}/')

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data['status'], 'fail')
        self.assertTrue(User.objects.filter(pk=super_user.pk).exists())

    def test_cannot_delete_self(self):
        self.api_client.force_authenticate(user=self.admin)
        response = self.api_client.delete(f'/api/admin/users/{self.admin.pk}/')

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data['status'], 'fail')
        self.assertTrue(User.objects.filter(pk=self.admin.pk).exists())

    def test_404_when_user_missing(self):
        self.api_client.force_authenticate(user=self.admin)
        response = self.api_client.delete('/api/admin/users/999999/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_non_admin_forbidden(self):
        other = _create_user('other@test.com')
        self.api_client.force_authenticate(user=other)
        response = self.api_client.delete(self.url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(User.objects.filter(pk=self.target.pk).exists())

    def test_unauthenticated_unauthorized(self):
        response = self.api_client.delete(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class AdminUserExportTests(TestCase):
    """GET /api/admin/users/<id>/export/"""

    EXPECTED_FILES = {
        'user.csv',
        'clients.csv',
        'addresses.csv',
        'services.csv',
        'quotes.csv',
        'quote_lines.csv',
        'invoices.csv',
        'invoice_lines.csv',
    }

    def setUp(self):
        self.api_client = APIClient()
        self.admin = _create_user('admin@test.com', is_staff=True)
        self.target = _create_user(
            'target@test.com',
            first_name='Jean',
            last_name='Dupont',
            company_name='ACME SAS',
        )
        _seed_user_data(self.target)
        self.url = f'/api/admin/users/{self.target.pk}/export/'

    def _read_zip(self, response):
        return zipfile.ZipFile(io.BytesIO(response.content))

    @staticmethod
    def _read_csv(archive, name):
        with archive.open(name) as fh:
            text = fh.read().decode('utf-8')
        return list(csv.reader(io.StringIO(text), delimiter=';'))

    def test_export_returns_zip(self):
        self.api_client.force_authenticate(user=self.admin)
        response = self.api_client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response['Content-Type'], 'application/zip')
        self.assertIn('attachment', response['Content-Disposition'])
        self.assertIn('.zip', response['Content-Disposition'])

    def test_archive_contains_expected_csv_files(self):
        self.api_client.force_authenticate(user=self.admin)
        response = self.api_client.get(self.url)

        archive = self._read_zip(response)
        self.assertEqual(set(archive.namelist()), self.EXPECTED_FILES)

    def test_user_csv_contains_target_data(self):
        self.api_client.force_authenticate(user=self.admin)
        response = self.api_client.get(self.url)

        archive = self._read_zip(response)
        rows = self._read_csv(archive, 'user.csv')

        self.assertEqual(len(rows), 2)  # header + 1 user
        header, data = rows
        self.assertIn('email', header)
        email_idx = header.index('email')
        self.assertEqual(data[email_idx], 'target@test.com')
        company_idx = header.index('company_name')
        self.assertEqual(data[company_idx], 'ACME SAS')

    def test_business_data_csvs_have_one_row(self):
        """Vérifie qu'un enregistrement seedé apparaît dans chaque CSV métier."""
        self.api_client.force_authenticate(user=self.admin)
        response = self.api_client.get(self.url)

        archive = self._read_zip(response)
        for name in ('clients.csv', 'addresses.csv', 'services.csv',
                     'quotes.csv', 'quote_lines.csv',
                     'invoices.csv', 'invoice_lines.csv'):
            with self.subTest(file=name):
                rows = self._read_csv(archive, name)
                self.assertEqual(len(rows), 2, f"{name} should have header + 1 row")

    def test_export_excludes_other_users_data(self):
        """Les données d'un autre utilisateur ne doivent pas fuiter."""
        intruder = _create_user('intruder@test.com')
        Client.objects.create(utilisateur=intruder, raison_sociale='LEAK')

        self.api_client.force_authenticate(user=self.admin)
        response = self.api_client.get(self.url)

        archive = self._read_zip(response)
        rows = self._read_csv(archive, 'clients.csv')
        labels = {row[1] for row in rows[1:]}  # column 'raison_sociale'
        self.assertNotIn('LEAK', labels)

    def test_export_includes_soft_deleted_quotes(self):
        """L'export RGPD doit inclure aussi les devis soft-deleted."""
        Quote.all_objects.filter(utilisateur=self.target).update(
            deleted_at='2026-01-01T00:00:00Z'
        )

        self.api_client.force_authenticate(user=self.admin)
        response = self.api_client.get(self.url)

        archive = self._read_zip(response)
        rows = self._read_csv(archive, 'quotes.csv')
        self.assertEqual(len(rows), 2)  # header + 1 soft-deleted quote

    def test_404_when_user_missing(self):
        self.api_client.force_authenticate(user=self.admin)
        response = self.api_client.get('/api/admin/users/999999/export/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_non_admin_forbidden(self):
        other = _create_user('other@test.com')
        self.api_client.force_authenticate(user=other)
        response = self.api_client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_unauthorized(self):
        response = self.api_client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
