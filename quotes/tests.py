from datetime import date, timedelta
from decimal import Decimal
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from accounts.models import User, UserConfiguration
from clients.models import Client
from .models import Quote, QuoteLine, QuoteHistory


class QuoteTestMixin:
    """Common fixtures for quote tests."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser', email='test@test.com', password='testpass123'
        )
        self.config = UserConfiguration.objects.create(
            user=self.user,
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

    def _create_quote(self, **kwargs):
        """Helper to create a quote via the API."""
        data = {
            'client_id': self.client_obj.pk,
            'objet': 'Test quote',
            'lignes': [
                {
                    'ordre': 1,
                    'libelle': 'Prestation',
                    'description': 'Description',
                    'quantite': '2.00',
                    'prix_unitaire_ht': '100.00',
                    'taux_tva': '20.00',
                }
            ],
        }
        data.update(kwargs)
        return self.api.post('/api/quotes/', data, format='json')


# =========================================================================
# MODEL
# =========================================================================

class QuoteModelTest(QuoteTestMixin, TestCase):

    def test_number_auto_generated_with_config_prefix(self):
        resp = self._create_quote()
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        quote = Quote.objects.get(pk=resp.data['data']['id'])
        year = date.today().year
        self.assertEqual(quote.numero, f'DEV-{year}-001')

    def test_number_increments(self):
        self._create_quote()
        resp2 = self._create_quote()
        year = date.today().year
        self.assertEqual(resp2.data['data']['numero'], f'DEV-{year}-002')

    def test_number_uses_custom_prefix(self):
        self.config.quote_prefix = 'QT'
        self.config.save()
        resp = self._create_quote()
        year = date.today().year
        self.assertTrue(resp.data['data']['numero'].startswith(f'QT-{year}-'))

    def test_is_editable_draft(self):
        resp = self._create_quote()
        quote = Quote.objects.get(pk=resp.data['data']['id'])
        self.assertTrue(quote.is_editable)

    def test_is_editable_false_if_sent(self):
        resp = self._create_quote()
        quote = Quote.objects.get(pk=resp.data['data']['id'])
        quote.statut = Quote.STATUT_ENVOYE
        quote.save()
        self.assertFalse(quote.is_editable)

    def test_is_deletable_draft(self):
        resp = self._create_quote()
        quote = Quote.objects.get(pk=resp.data['data']['id'])
        self.assertTrue(quote.is_deletable)

    def test_is_deletable_false_if_accepted(self):
        resp = self._create_quote()
        quote = Quote.objects.get(pk=resp.data['data']['id'])
        quote.statut = Quote.STATUT_ACCEPTE
        quote.save()
        self.assertFalse(quote.is_deletable)

    def test_delete_forbidden_if_not_draft(self):
        resp = self._create_quote()
        quote = Quote.objects.get(pk=resp.data['data']['id'])
        quote.statut = Quote.STATUT_ENVOYE
        quote.save()
        with self.assertRaises(ValueError):
            quote.delete()

    def test_soft_delete_cascade(self):
        resp = self._create_quote()
        quote = Quote.objects.get(pk=resp.data['data']['id'])
        line_id = quote.lignes.first().pk
        history_id = quote.historique.first().pk
        quote.delete()
        self.assertIsNone(Quote.objects.filter(pk=quote.pk).first())
        self.assertIsNotNone(Quote.all_objects.get(pk=quote.pk).deleted_at)
        self.assertIsNotNone(QuoteLine.all_objects.get(pk=line_id).deleted_at)
        self.assertIsNotNone(QuoteHistory.all_objects.get(pk=history_id).deleted_at)

    def test_calculate_totals(self):
        resp = self._create_quote()
        quote = Quote.objects.get(pk=resp.data['data']['id'])
        # 2 * 100 = 200 HT, VAT 20% = 40, TTC = 240
        self.assertEqual(quote.total_ht, Decimal('200.00'))
        self.assertEqual(quote.total_tva, Decimal('40.00'))
        self.assertEqual(quote.total_ttc, Decimal('240.00'))


# =========================================================================
# VALIDITY DATE
# =========================================================================

class QuoteValidityDateTest(QuoteTestMixin, TestCase):

    def test_validity_date_auto_calculated(self):
        resp = self._create_quote()
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        quote = Quote.objects.get(pk=resp.data['data']['id'])
        expected = quote.date_emission + timedelta(days=30)
        self.assertEqual(quote.date_validite, expected)

    def test_validity_date_provided_respected(self):
        custom_date = (date.today() + timedelta(days=60)).isoformat()
        resp = self._create_quote(date_validite=custom_date)
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        quote = Quote.objects.get(pk=resp.data['data']['id'])
        self.assertEqual(quote.date_validite, date.today() + timedelta(days=60))

    def test_validity_date_uses_custom_config(self):
        self.config.quote_validity_days = 15
        self.config.save()
        resp = self._create_quote()
        quote = Quote.objects.get(pk=resp.data['data']['id'])
        expected = quote.date_emission + timedelta(days=15)
        self.assertEqual(quote.date_validite, expected)


# =========================================================================
# API CRUD
# =========================================================================

class QuoteAPITest(QuoteTestMixin, TestCase):

    def test_create_quote(self):
        resp = self._create_quote()
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data['status'], 'success')
        self.assertIn('numero', resp.data['data'])
        self.assertEqual(resp.data['data']['statut'], 'BROUILLON')

    def test_create_quote_creates_history(self):
        resp = self._create_quote()
        quote = Quote.objects.get(pk=resp.data['data']['id'])
        hist = quote.historique.first()
        self.assertIsNone(hist.ancien_statut)
        self.assertEqual(hist.nouveau_statut, 'BROUILLON')

    def test_list_quotes_filtered_by_user(self):
        self._create_quote()
        other_user = User.objects.create_user(
            username='other', email='other@test.com', password='pass123'
        )
        UserConfiguration.objects.create(user=other_user, quote_prefix='OTH')
        other_client = Client.objects.create(
            utilisateur=other_user, raison_sociale='Autre Client'
        )
        other_api = APIClient()
        other_api.force_authenticate(user=other_user)
        other_api.post('/api/quotes/', {
            'client_id': other_client.pk,
            'objet': 'Other quote',
            'lignes': [{'ordre': 1, 'libelle': 'L', 'quantite': '1', 'prix_unitaire_ht': '10', 'taux_tva': '20'}],
        }, format='json')

        resp = self.api.get('/api/quotes/')
        self.assertEqual(resp.data['data']['count'], 1)

    def test_update_draft_ok(self):
        resp = self._create_quote()
        quote_id = resp.data['data']['id']
        resp2 = self.api.patch(
            f'/api/quotes/{quote_id}/',
            {'objet': 'Modified'},
            format='json',
        )
        self.assertEqual(resp2.status_code, status.HTTP_200_OK)
        self.assertEqual(resp2.data['status'], 'success')
        self.assertEqual(resp2.data['data']['objet'], 'Modified')

    def test_update_non_draft_forbidden(self):
        resp = self._create_quote()
        quote_id = resp.data['data']['id']
        self.api.post(f'/api/quotes/{quote_id}/changer_statut/', {'statut': 'ENVOYE'}, format='json')
        resp2 = self.api.patch(
            f'/api/quotes/{quote_id}/',
            {'objet': 'Modified'},
            format='json',
        )
        self.assertEqual(resp2.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp2.data['status'], 'fail')

    def test_put_non_draft_forbidden(self):
        resp = self._create_quote()
        quote_id = resp.data['data']['id']
        self.api.post(f'/api/quotes/{quote_id}/changer_statut/', {'statut': 'ENVOYE'}, format='json')
        resp2 = self.api.put(
            f'/api/quotes/{quote_id}/',
            {
                'client_id': self.client_obj.pk,
                'objet': 'Modified',
                'date_validite': (date.today() + timedelta(days=30)).isoformat(),
                'lignes': [{'ordre': 1, 'libelle': 'L', 'quantite': '1', 'prix_unitaire_ht': '10', 'taux_tva': '20'}],
            },
            format='json',
        )
        self.assertEqual(resp2.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp2.data['status'], 'fail')

    def test_delete_draft_ok(self):
        resp = self._create_quote()
        quote_id = resp.data['data']['id']
        resp2 = self.api.delete(f'/api/quotes/{quote_id}/')
        self.assertEqual(resp2.status_code, status.HTTP_204_NO_CONTENT)

    def test_delete_non_draft_forbidden(self):
        resp = self._create_quote()
        quote_id = resp.data['data']['id']
        self.api.post(f'/api/quotes/{quote_id}/changer_statut/', {'statut': 'ENVOYE'}, format='json')
        resp2 = self.api.delete(f'/api/quotes/{quote_id}/')
        self.assertEqual(resp2.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp2.data['status'], 'fail')

    def test_client_not_modifiable_on_update(self):
        other_client = Client.objects.create(
            utilisateur=self.user, raison_sociale='Other Client'
        )
        resp = self._create_quote()
        quote_id = resp.data['data']['id']
        resp2 = self.api.patch(
            f'/api/quotes/{quote_id}/',
            {'client_id': other_client.pk},
            format='json',
        )
        self.assertEqual(resp2.status_code, status.HTTP_200_OK)
        quote = Quote.objects.get(pk=quote_id)
        self.assertEqual(quote.client_id, self.client_obj.pk)


# =========================================================================
# CHANGE STATUS
# =========================================================================

class QuoteChangeStatusTest(QuoteTestMixin, TestCase):

    def test_change_status_ok(self):
        resp = self._create_quote()
        quote_id = resp.data['data']['id']
        resp2 = self.api.post(
            f'/api/quotes/{quote_id}/changer_statut/',
            {'statut': 'ENVOYE'},
            format='json',
        )
        self.assertEqual(resp2.status_code, status.HTTP_200_OK)
        self.assertEqual(resp2.data['status'], 'success')

    def test_change_status_creates_history(self):
        resp = self._create_quote()
        quote_id = resp.data['data']['id']
        self.api.post(f'/api/quotes/{quote_id}/changer_statut/', {'statut': 'ENVOYE'}, format='json')
        quote = Quote.objects.get(pk=quote_id)
        hist = quote.historique.order_by('-created_at').first()
        self.assertEqual(hist.ancien_statut, 'BROUILLON')
        self.assertEqual(hist.nouveau_statut, 'ENVOYE')

    def test_change_status_invalid(self):
        resp = self._create_quote()
        quote_id = resp.data['data']['id']
        resp2 = self.api.post(
            f'/api/quotes/{quote_id}/changer_statut/',
            {'statut': 'NONEXISTENT'},
            format='json',
        )
        self.assertEqual(resp2.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp2.data['status'], 'fail')

    def test_unauthenticated_access_denied(self):
        api = APIClient()
        resp = api.get('/api/quotes/')
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(resp.data['status'], 'fail')
