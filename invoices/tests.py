from datetime import date, timedelta
from decimal import Decimal
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from accounts.models import User, UserConfiguration
from clients.models import Client
from quotes.models import Quote, QuoteLine, QuoteHistory
from .models import Invoice, InvoiceLine, InvoiceHistory


class InvoiceTestMixin:
    """Common fixtures for invoice tests."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser', email='test@test.com', password='testpass123'
        )
        self.config = UserConfiguration.objects.create(
            user=self.user,
            invoice_prefix='FAC',
            next_invoice_number=1,
            payment_deadline_days=30,
            quote_prefix='DEV',
            next_quote_number=1,
            quote_validity_days=30,
        )
        self.client_obj = Client.objects.create(
            utilisateur=self.user,
            raison_sociale='Client Test',
        )
        self.api = APIClient()
        self.api.force_authenticate(user=self.user)

    def _line_data(self, **kwargs):
        data = {
            'ordre': 1,
            'libelle': 'Prestation',
            'description': 'Description',
            'quantite': '2.00',
            'prix_unitaire_ht': '100.00',
            'taux_tva': '20.00',
        }
        data.update(kwargs)
        return data

    def _create_invoice(self, **kwargs):
        """Helper to create an invoice via the API."""
        data = {
            'client_id': self.client_obj.pk,
            'objet': 'Test invoice',
            'lignes': [self._line_data()],
        }
        data.update(kwargs)
        return self.api.post('/api/invoices/', data, format='json')

    def _create_accepted_quote(self):
        """Helper to create a quote in ACCEPTED status."""
        resp = self.api.post('/api/quotes/', {
            'client_id': self.client_obj.pk,
            'objet': 'Quote for invoice',
            'lignes': [self._line_data()],
        }, format='json')
        quote_id = resp.data['data']['id']
        self.api.post(f'/api/quotes/{quote_id}/changer_statut/', {'statut': 'ENVOYE'}, format='json')
        self.api.post(f'/api/quotes/{quote_id}/changer_statut/', {'statut': 'ACCEPTE'}, format='json')
        return quote_id


# MODEL
class InvoiceModelTest(InvoiceTestMixin, TestCase):

    def test_is_editable_draft(self):
        resp = self._create_invoice()
        invoice = Invoice.objects.get(pk=resp.data['data']['id'])
        self.assertTrue(invoice.is_editable)

    def test_is_editable_false_if_sent(self):
        resp = self._create_invoice()
        invoice = Invoice.objects.get(pk=resp.data['data']['id'])
        invoice.statut = Invoice.STATUT_ENVOYEE
        invoice.save()
        self.assertFalse(invoice.is_editable)

    def test_is_deletable_draft(self):
        resp = self._create_invoice()
        invoice = Invoice.objects.get(pk=resp.data['data']['id'])
        self.assertTrue(invoice.is_deletable)

    def test_is_deletable_false_if_sent(self):
        resp = self._create_invoice()
        invoice = Invoice.objects.get(pk=resp.data['data']['id'])
        invoice.statut = Invoice.STATUT_ENVOYEE
        invoice.save()
        self.assertFalse(invoice.is_deletable)

    def test_delete_forbidden_if_not_draft(self):
        resp = self._create_invoice()
        invoice = Invoice.objects.get(pk=resp.data['data']['id'])
        invoice.statut = Invoice.STATUT_ENVOYEE
        invoice.save()
        with self.assertRaises(PermissionError):
            invoice.delete()

    def test_soft_delete_cascade(self):
        resp = self._create_invoice()
        invoice = Invoice.objects.get(pk=resp.data['data']['id'])
        invoice.delete()
        self.assertIsNone(Invoice.objects.filter(pk=invoice.pk).first())
        self.assertIsNotNone(Invoice.all_objects.get(pk=invoice.pk).deleted_at)

    def test_calculate_totals(self):
        resp = self._create_invoice()
        invoice = Invoice.objects.get(pk=resp.data['data']['id'])
        # 2 * 100 = 200 HT, VAT 20% = 40, TTC = 240
        self.assertEqual(invoice.total_ht, Decimal('200.00'))
        self.assertEqual(invoice.total_tva, Decimal('40.00'))
        self.assertEqual(invoice.total_ttc, Decimal('240.00'))


# API CRUD
class InvoiceAPITest(InvoiceTestMixin, TestCase):

    def test_create_invoice(self):
        resp = self._create_invoice()
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data['status'], 'success')
        self.assertEqual(resp.data['data']['statut'], 'BROUILLON')

    def test_create_invoice_creates_history(self):
        resp = self._create_invoice()
        invoice = Invoice.objects.get(pk=resp.data['data']['id'])
        hist = invoice.historique.first()
        self.assertIsNone(hist.ancien_statut)
        self.assertEqual(hist.nouveau_statut, 'BROUILLON')

    def test_due_date_auto_calculated(self):
        resp = self._create_invoice()
        invoice = Invoice.objects.get(pk=resp.data['data']['id'])
        expected = invoice.date_emission + timedelta(days=30)
        self.assertEqual(invoice.date_echeance, expected)

    def test_due_date_provided_respected(self):
        custom_date = (date.today() + timedelta(days=60)).isoformat()
        resp = self._create_invoice(date_echeance=custom_date)
        invoice = Invoice.objects.get(pk=resp.data['data']['id'])
        self.assertEqual(invoice.date_echeance, date.today() + timedelta(days=60))

    def test_list_invoices_filtered_by_user(self):
        self._create_invoice()
        other_user = User.objects.create_user(
            username='other', email='other@test.com', password='pass123'
        )
        UserConfiguration.objects.create(user=other_user)
        other_client = Client.objects.create(
            utilisateur=other_user, raison_sociale='Other Client'
        )
        other_api = APIClient()
        other_api.force_authenticate(user=other_user)
        other_api.post('/api/invoices/', {
            'client_id': other_client.pk,
            'objet': 'Other invoice',
            'lignes': [self._line_data()],
        }, format='json')

        resp = self.api.get('/api/invoices/')
        self.assertEqual(resp.data['data']['count'], 1)

    def test_update_draft_ok(self):
        resp = self._create_invoice()
        invoice_id = resp.data['data']['id']
        resp2 = self.api.patch(
            f'/api/invoices/{invoice_id}/',
            {'objet': 'Modified', 'lignes': [self._line_data()]},
            format='json',
        )
        self.assertEqual(resp2.status_code, status.HTTP_200_OK)
        self.assertEqual(resp2.data['status'], 'success')
        self.assertEqual(resp2.data['data']['objet'], 'Modified')

    def test_update_non_draft_forbidden(self):
        resp = self._create_invoice()
        invoice_id = resp.data['data']['id']
        self.api.post(
            f'/api/invoices/{invoice_id}/changer_statut/',
            {'statut': 'ENVOYEE'},
            format='json',
        )
        resp2 = self.api.patch(
            f'/api/invoices/{invoice_id}/',
            {'objet': 'Modified', 'lignes': [self._line_data()]},
            format='json',
        )
        self.assertEqual(resp2.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp2.data['status'], 'fail')

    def test_delete_draft_ok(self):
        resp = self._create_invoice()
        invoice_id = resp.data['data']['id']
        resp2 = self.api.delete(f'/api/invoices/{invoice_id}/')
        self.assertEqual(resp2.status_code, status.HTTP_204_NO_CONTENT)

    def test_delete_non_draft_forbidden(self):
        resp = self._create_invoice()
        invoice_id = resp.data['data']['id']
        self.api.post(
            f'/api/invoices/{invoice_id}/changer_statut/',
            {'statut': 'ENVOYEE'},
            format='json',
        )
        resp2 = self.api.delete(f'/api/invoices/{invoice_id}/')
        self.assertEqual(resp2.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(resp2.data['status'], 'fail')

    def test_client_not_modifiable_on_update(self):
        other_client = Client.objects.create(
            utilisateur=self.user, raison_sociale='Other Client'
        )
        resp = self._create_invoice()
        invoice_id = resp.data['data']['id']
        resp2 = self.api.patch(
            f'/api/invoices/{invoice_id}/',
            {'client_id': other_client.pk, 'lignes': [self._line_data()]},
            format='json',
        )
        self.assertEqual(resp2.status_code, status.HTTP_200_OK)
        invoice = Invoice.objects.get(pk=invoice_id)
        self.assertEqual(invoice.client_id, self.client_obj.pk)

    def test_unauthenticated_access_denied(self):
        api = APIClient()
        resp = api.get('/api/invoices/')
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(resp.data['status'], 'fail')



# CHANGE STATUS
class InvoiceChangeStatusTest(InvoiceTestMixin, TestCase):

    def test_draft_to_sent(self):
        resp = self._create_invoice()
        invoice_id = resp.data['data']['id']
        resp2 = self.api.post(
            f'/api/invoices/{invoice_id}/changer_statut/',
            {'statut': 'ENVOYEE'},
            format='json',
        )
        self.assertEqual(resp2.status_code, status.HTTP_200_OK)
        self.assertEqual(resp2.data['status'], 'success')
        self.assertEqual(resp2.data['data']['statut'], 'ENVOYEE')

    def test_number_generated_on_sent(self):
        resp = self._create_invoice()
        invoice_id = resp.data['data']['id']
        self.assertIsNone(resp.data['data']['numero'])
        resp2 = self.api.post(
            f'/api/invoices/{invoice_id}/changer_statut/',
            {'statut': 'ENVOYEE'},
            format='json',
        )
        year = date.today().year
        self.assertEqual(resp2.data['data']['numero'], f'FAC-{year}-001')

    def test_invalid_transition_draft_to_paid(self):
        resp = self._create_invoice()
        invoice_id = resp.data['data']['id']
        resp2 = self.api.post(
            f'/api/invoices/{invoice_id}/changer_statut/',
            {'statut': 'PAYEE'},
            format='json',
        )
        self.assertEqual(resp2.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp2.data['status'], 'fail')

    def test_sent_to_paid(self):
        resp = self._create_invoice()
        invoice_id = resp.data['data']['id']
        self.api.post(f'/api/invoices/{invoice_id}/changer_statut/', {'statut': 'ENVOYEE'}, format='json')
        resp2 = self.api.post(
            f'/api/invoices/{invoice_id}/changer_statut/',
            {'statut': 'PAYEE'},
            format='json',
        )
        self.assertEqual(resp2.status_code, status.HTTP_200_OK)
        self.assertEqual(resp2.data['status'], 'success')
        self.assertEqual(resp2.data['data']['statut'], 'PAYEE')

    def test_sent_to_overdue(self):
        resp = self._create_invoice()
        invoice_id = resp.data['data']['id']
        self.api.post(f'/api/invoices/{invoice_id}/changer_statut/', {'statut': 'ENVOYEE'}, format='json')
        resp2 = self.api.post(
            f'/api/invoices/{invoice_id}/changer_statut/',
            {'statut': 'EN_RETARD'},
            format='json',
        )
        self.assertEqual(resp2.status_code, status.HTTP_200_OK)
        self.assertEqual(resp2.data['status'], 'success')

    def test_overdue_to_paid(self):
        resp = self._create_invoice()
        invoice_id = resp.data['data']['id']
        self.api.post(f'/api/invoices/{invoice_id}/changer_statut/', {'statut': 'ENVOYEE'}, format='json')
        self.api.post(f'/api/invoices/{invoice_id}/changer_statut/', {'statut': 'EN_RETARD'}, format='json')
        resp2 = self.api.post(
            f'/api/invoices/{invoice_id}/changer_statut/',
            {'statut': 'PAYEE'},
            format='json',
        )
        self.assertEqual(resp2.status_code, status.HTTP_200_OK)
        self.assertEqual(resp2.data['status'], 'success')

    def test_change_status_creates_history(self):
        resp = self._create_invoice()
        invoice_id = resp.data['data']['id']
        self.api.post(f'/api/invoices/{invoice_id}/changer_statut/', {'statut': 'ENVOYEE'}, format='json')
        invoice = Invoice.objects.get(pk=invoice_id)
        hist = invoice.historique.order_by('-created_at').first()
        self.assertEqual(hist.ancien_statut, 'BROUILLON')
        self.assertEqual(hist.nouveau_statut, 'ENVOYEE')

    def test_status_required(self):
        resp = self._create_invoice()
        invoice_id = resp.data['data']['id']
        resp2 = self.api.post(
            f'/api/invoices/{invoice_id}/changer_statut/',
            {},
            format='json',
        )
        self.assertEqual(resp2.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp2.data['status'], 'fail')



# CREATE FROM QUOTE
class InvoiceFromQuoteTest(InvoiceTestMixin, TestCase):

    def test_from_accepted_quote(self):
        quote_id = self._create_accepted_quote()
        resp = self.api.post(
            '/api/invoices/from-devis/',
            {'devis_id': quote_id},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data['status'], 'success')
        self.assertEqual(resp.data['data']['statut'], 'ENVOYEE')
        self.assertEqual(resp.data['data']['devis_origine'], quote_id)

    def test_from_quote_copies_lines(self):
        quote_id = self._create_accepted_quote()
        resp = self.api.post(
            '/api/invoices/from-devis/',
            {'devis_id': quote_id},
            format='json',
        )
        invoice = Invoice.objects.get(pk=resp.data['data']['id'])
        self.assertEqual(invoice.lignes.count(), 1)
        line = invoice.lignes.first()
        self.assertEqual(line.libelle, 'Prestation')
        self.assertEqual(line.quantite, Decimal('2.00'))
        self.assertEqual(line.prix_unitaire_ht, Decimal('100.00'))

    def test_from_quote_calculates_totals(self):
        quote_id = self._create_accepted_quote()
        resp = self.api.post(
            '/api/invoices/from-devis/',
            {'devis_id': quote_id},
            format='json',
        )
        invoice = Invoice.objects.get(pk=resp.data['data']['id'])
        self.assertEqual(invoice.total_ht, Decimal('200.00'))
        self.assertEqual(invoice.total_ttc, Decimal('240.00'))

    def test_from_sent_quote_sets_accepted(self):
        """A SENT quote is automatically set to ACCEPTED."""
        resp = self.api.post('/api/quotes/', {
            'client_id': self.client_obj.pk,
            'objet': 'Sent quote',
            'lignes': [self._line_data()],
        }, format='json')
        quote_id = resp.data['data']['id']
        self.api.post(f'/api/quotes/{quote_id}/changer_statut/', {'statut': 'ENVOYE'}, format='json')

        resp2 = self.api.post(
            '/api/invoices/from-devis/',
            {'devis_id': quote_id},
            format='json',
        )
        self.assertEqual(resp2.status_code, status.HTTP_201_CREATED)
        quote = Quote.objects.get(pk=quote_id)
        self.assertEqual(quote.statut, Quote.STATUT_ACCEPTE)

    def test_from_draft_quote_forbidden(self):
        resp = self.api.post('/api/quotes/', {
            'client_id': self.client_obj.pk,
            'objet': 'Draft quote',
            'lignes': [self._line_data()],
        }, format='json')
        quote_id = resp.data['data']['id']
        resp2 = self.api.post(
            '/api/invoices/from-devis/',
            {'devis_id': quote_id},
            format='json',
        )
        self.assertEqual(resp2.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp2.data['status'], 'fail')

    def test_from_refused_quote_forbidden(self):
        resp = self.api.post('/api/quotes/', {
            'client_id': self.client_obj.pk,
            'objet': 'Refused quote',
            'lignes': [self._line_data()],
        }, format='json')
        quote_id = resp.data['data']['id']
        self.api.post(f'/api/quotes/{quote_id}/changer_statut/', {'statut': 'REFUSE'}, format='json')
        resp2 = self.api.post(
            '/api/invoices/from-devis/',
            {'devis_id': quote_id},
            format='json',
        )
        self.assertEqual(resp2.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp2.data['status'], 'fail')

    def test_from_quote_duplicate_forbidden(self):
        quote_id = self._create_accepted_quote()
        self.api.post('/api/invoices/from-devis/', {'devis_id': quote_id}, format='json')
        resp2 = self.api.post(
            '/api/invoices/from-devis/',
            {'devis_id': quote_id},
            format='json',
        )
        self.assertEqual(resp2.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp2.data['status'], 'fail')

    def test_from_nonexistent_quote(self):
        resp = self.api.post(
            '/api/invoices/from-devis/',
            {'devis_id': 99999},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data['status'], 'fail')
