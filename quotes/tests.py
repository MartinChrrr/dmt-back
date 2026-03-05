from datetime import date, timedelta
from decimal import Decimal
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from accounts.models import User, UserConfiguration
from clients.models import Client
from .models import Devis, LigneDevis, HistoriqueDevis


class QuoteTestMixin:
    """Fixtures communes pour les tests de devis."""

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

    def _create_devis(self, **kwargs):
        """Helper pour créer un devis via l'API."""
        data = {
            'client_id': self.client_obj.pk,
            'objet': 'Devis test',
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
# MODELE
# =========================================================================

class DevisModelTest(QuoteTestMixin, TestCase):

    def test_numero_auto_genere_avec_prefix_config(self):
        resp = self._create_devis()
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        devis = Devis.objects.get(pk=resp.data['id'])
        year = date.today().year
        self.assertEqual(devis.numero, f'DEV-{year}-001')

    def test_numero_incremente(self):
        self._create_devis()
        resp2 = self._create_devis()
        year = date.today().year
        self.assertEqual(resp2.data['numero'], f'DEV-{year}-002')

    def test_numero_utilise_prefix_personnalise(self):
        self.config.quote_prefix = 'QT'
        self.config.save()
        resp = self._create_devis()
        year = date.today().year
        self.assertTrue(resp.data['numero'].startswith(f'QT-{year}-'))

    def test_est_modifiable_brouillon(self):
        resp = self._create_devis()
        devis = Devis.objects.get(pk=resp.data['id'])
        self.assertTrue(devis.est_modifiable)

    def test_est_modifiable_false_si_envoye(self):
        resp = self._create_devis()
        devis = Devis.objects.get(pk=resp.data['id'])
        devis.statut = Devis.STATUT_ENVOYE
        devis.save()
        self.assertFalse(devis.est_modifiable)

    def test_est_supprimable_brouillon(self):
        resp = self._create_devis()
        devis = Devis.objects.get(pk=resp.data['id'])
        self.assertTrue(devis.est_supprimable)

    def test_est_supprimable_false_si_accepte(self):
        resp = self._create_devis()
        devis = Devis.objects.get(pk=resp.data['id'])
        devis.statut = Devis.STATUT_ACCEPTE
        devis.save()
        self.assertFalse(devis.est_supprimable)

    def test_delete_interdit_si_non_brouillon(self):
        resp = self._create_devis()
        devis = Devis.objects.get(pk=resp.data['id'])
        devis.statut = Devis.STATUT_ENVOYE
        devis.save()
        with self.assertRaises(ValueError):
            devis.delete()

    def test_soft_delete_cascade(self):
        resp = self._create_devis()
        devis = Devis.objects.get(pk=resp.data['id'])
        ligne_id = devis.lignes.first().pk
        historique_id = devis.historique.first().pk
        devis.delete()
        self.assertIsNone(Devis.objects.filter(pk=devis.pk).first())
        self.assertIsNotNone(Devis.all_objects.get(pk=devis.pk).deleted_at)
        self.assertIsNotNone(LigneDevis.all_objects.get(pk=ligne_id).deleted_at)
        self.assertIsNotNone(HistoriqueDevis.all_objects.get(pk=historique_id).deleted_at)

    def test_calculer_totaux(self):
        resp = self._create_devis()
        devis = Devis.objects.get(pk=resp.data['id'])
        # 2 * 100 = 200 HT, TVA 20% = 40, TTC = 240
        self.assertEqual(devis.total_ht, Decimal('200.00'))
        self.assertEqual(devis.total_tva, Decimal('40.00'))
        self.assertEqual(devis.total_ttc, Decimal('240.00'))


# =========================================================================
# DATE VALIDITE
# =========================================================================

class DevisDateValiditeTest(QuoteTestMixin, TestCase):

    def test_date_validite_auto_calculee(self):
        resp = self._create_devis()
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        devis = Devis.objects.get(pk=resp.data['id'])
        expected = devis.date_emission + timedelta(days=30)
        self.assertEqual(devis.date_validite, expected)

    def test_date_validite_fournie_respectee(self):
        custom_date = (date.today() + timedelta(days=60)).isoformat()
        resp = self._create_devis(date_validite=custom_date)
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        devis = Devis.objects.get(pk=resp.data['id'])
        self.assertEqual(devis.date_validite, date.today() + timedelta(days=60))

    def test_date_validite_utilise_config_personnalisee(self):
        self.config.quote_validity_days = 15
        self.config.save()
        resp = self._create_devis()
        devis = Devis.objects.get(pk=resp.data['id'])
        expected = devis.date_emission + timedelta(days=15)
        self.assertEqual(devis.date_validite, expected)


# =========================================================================
# API CRUD
# =========================================================================

class DevisAPITest(QuoteTestMixin, TestCase):

    def test_create_devis(self):
        resp = self._create_devis()
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertIn('numero', resp.data)
        self.assertEqual(resp.data['statut'], 'BROUILLON')

    def test_create_devis_cree_historique(self):
        resp = self._create_devis()
        devis = Devis.objects.get(pk=resp.data['id'])
        hist = devis.historique.first()
        self.assertIsNone(hist.ancien_statut)
        self.assertEqual(hist.nouveau_statut, 'BROUILLON')

    def test_list_devis_filtre_par_utilisateur(self):
        self._create_devis()
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
            'objet': 'Autre devis',
            'lignes': [{'ordre': 1, 'libelle': 'L', 'quantite': '1', 'prix_unitaire_ht': '10', 'taux_tva': '20'}],
        }, format='json')

        resp = self.api.get('/api/quotes/')
        self.assertEqual(resp.data['count'], 1)

    def test_update_brouillon_ok(self):
        resp = self._create_devis()
        devis_id = resp.data['id']
        resp2 = self.api.patch(
            f'/api/quotes/{devis_id}/',
            {'objet': 'Modifié'},
            format='json',
        )
        self.assertEqual(resp2.status_code, status.HTTP_200_OK)
        self.assertEqual(resp2.data['objet'], 'Modifié')

    def test_update_non_brouillon_interdit(self):
        resp = self._create_devis()
        devis_id = resp.data['id']
        self.api.post(f'/api/quotes/{devis_id}/changer_statut/', {'statut': 'ENVOYE'}, format='json')
        resp2 = self.api.patch(
            f'/api/quotes/{devis_id}/',
            {'objet': 'Modifié'},
            format='json',
        )
        self.assertEqual(resp2.status_code, status.HTTP_400_BAD_REQUEST)

    def test_put_non_brouillon_interdit(self):
        resp = self._create_devis()
        devis_id = resp.data['id']
        self.api.post(f'/api/quotes/{devis_id}/changer_statut/', {'statut': 'ENVOYE'}, format='json')
        resp2 = self.api.put(
            f'/api/quotes/{devis_id}/',
            {
                'client_id': self.client_obj.pk,
                'objet': 'Modifié',
                'date_validite': (date.today() + timedelta(days=30)).isoformat(),
                'lignes': [{'ordre': 1, 'libelle': 'L', 'quantite': '1', 'prix_unitaire_ht': '10', 'taux_tva': '20'}],
            },
            format='json',
        )
        self.assertEqual(resp2.status_code, status.HTTP_400_BAD_REQUEST)

    def test_delete_brouillon_ok(self):
        resp = self._create_devis()
        devis_id = resp.data['id']
        resp2 = self.api.delete(f'/api/quotes/{devis_id}/')
        self.assertEqual(resp2.status_code, status.HTTP_204_NO_CONTENT)

    def test_delete_non_brouillon_interdit(self):
        resp = self._create_devis()
        devis_id = resp.data['id']
        self.api.post(f'/api/quotes/{devis_id}/changer_statut/', {'statut': 'ENVOYE'}, format='json')
        resp2 = self.api.delete(f'/api/quotes/{devis_id}/')
        self.assertEqual(resp2.status_code, status.HTTP_400_BAD_REQUEST)

    def test_client_non_modifiable_en_update(self):
        other_client = Client.objects.create(
            utilisateur=self.user, raison_sociale='Autre Client'
        )
        resp = self._create_devis()
        devis_id = resp.data['id']
        resp2 = self.api.patch(
            f'/api/quotes/{devis_id}/',
            {'client_id': other_client.pk},
            format='json',
        )
        self.assertEqual(resp2.status_code, status.HTTP_200_OK)
        devis = Devis.objects.get(pk=devis_id)
        self.assertEqual(devis.client_id, self.client_obj.pk)


# =========================================================================
# CHANGER STATUT
# =========================================================================

class DevisChangerStatutTest(QuoteTestMixin, TestCase):

    def test_changer_statut_ok(self):
        resp = self._create_devis()
        devis_id = resp.data['id']
        resp2 = self.api.post(
            f'/api/quotes/{devis_id}/changer_statut/',
            {'statut': 'ENVOYE'},
            format='json',
        )
        self.assertEqual(resp2.status_code, status.HTTP_200_OK)

    def test_changer_statut_cree_historique(self):
        resp = self._create_devis()
        devis_id = resp.data['id']
        self.api.post(f'/api/quotes/{devis_id}/changer_statut/', {'statut': 'ENVOYE'}, format='json')
        devis = Devis.objects.get(pk=devis_id)
        hist = devis.historique.order_by('-created_at').first()
        self.assertEqual(hist.ancien_statut, 'BROUILLON')
        self.assertEqual(hist.nouveau_statut, 'ENVOYE')

    def test_changer_statut_invalide(self):
        resp = self._create_devis()
        devis_id = resp.data['id']
        resp2 = self.api.post(
            f'/api/quotes/{devis_id}/changer_statut/',
            {'statut': 'INEXISTANT'},
            format='json',
        )
        self.assertEqual(resp2.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unauthenticated_access_denied(self):
        api = APIClient()
        resp = api.get('/api/quotes/')
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)
