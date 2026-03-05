from datetime import date, timedelta
from decimal import Decimal
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from accounts.models import User, UserConfiguration
from clients.models import Client
from quotes.models import Devis, LigneDevis, HistoriqueDevis
from .models import Facture, LigneFacture, HistoriqueFacture


class InvoiceTestMixin:
    """Fixtures communes pour les tests de factures."""

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

    def _ligne_data(self, **kwargs):
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

    def _create_facture(self, **kwargs):
        """Helper pour créer une facture via l'API."""
        data = {
            'client_id': self.client_obj.pk,
            'objet': 'Facture test',
            'lignes': [self._ligne_data()],
        }
        data.update(kwargs)
        return self.api.post('/api/invoices/', data, format='json')

    def _create_devis_accepte(self):
        """Helper pour créer un devis en statut ACCEPTE."""
        resp = self.api.post('/api/quotes/', {
            'client_id': self.client_obj.pk,
            'objet': 'Devis pour facture',
            'lignes': [self._ligne_data()],
        }, format='json')
        devis_id = resp.data['id']
        self.api.post(f'/api/quotes/{devis_id}/changer_statut/', {'statut': 'ENVOYE'}, format='json')
        self.api.post(f'/api/quotes/{devis_id}/changer_statut/', {'statut': 'ACCEPTE'}, format='json')
        return devis_id


# =========================================================================
# MODELE
# =========================================================================

class FactureModelTest(InvoiceTestMixin, TestCase):

    def test_est_modifiable_brouillon(self):
        resp = self._create_facture()
        facture = Facture.objects.get(pk=resp.data['id'])
        self.assertTrue(facture.est_modifiable)

    def test_est_modifiable_false_si_envoyee(self):
        resp = self._create_facture()
        facture = Facture.objects.get(pk=resp.data['id'])
        facture.statut = Facture.STATUT_ENVOYEE
        facture.save()
        self.assertFalse(facture.est_modifiable)

    def test_est_supprimable_brouillon(self):
        resp = self._create_facture()
        facture = Facture.objects.get(pk=resp.data['id'])
        self.assertTrue(facture.est_supprimable)

    def test_est_supprimable_false_si_envoyee(self):
        resp = self._create_facture()
        facture = Facture.objects.get(pk=resp.data['id'])
        facture.statut = Facture.STATUT_ENVOYEE
        facture.save()
        self.assertFalse(facture.est_supprimable)

    def test_delete_interdit_si_non_brouillon(self):
        resp = self._create_facture()
        facture = Facture.objects.get(pk=resp.data['id'])
        facture.statut = Facture.STATUT_ENVOYEE
        facture.save()
        with self.assertRaises(PermissionError):
            facture.delete()

    def test_soft_delete_cascade(self):
        resp = self._create_facture()
        facture = Facture.objects.get(pk=resp.data['id'])
        facture.delete()
        self.assertIsNone(Facture.objects.filter(pk=facture.pk).first())
        self.assertIsNotNone(Facture.all_objects.get(pk=facture.pk).deleted_at)

    def test_calculer_totaux(self):
        resp = self._create_facture()
        facture = Facture.objects.get(pk=resp.data['id'])
        # 2 * 100 = 200 HT, TVA 20% = 40, TTC = 240
        self.assertEqual(facture.total_ht, Decimal('200.00'))
        self.assertEqual(facture.total_tva, Decimal('40.00'))
        self.assertEqual(facture.total_ttc, Decimal('240.00'))


# =========================================================================
# API CRUD
# =========================================================================

class FactureAPITest(InvoiceTestMixin, TestCase):

    def test_create_facture(self):
        resp = self._create_facture()
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data['statut'], 'BROUILLON')

    def test_create_facture_cree_historique(self):
        resp = self._create_facture()
        facture = Facture.objects.get(pk=resp.data['id'])
        hist = facture.historique.first()
        self.assertIsNone(hist.ancien_statut)
        self.assertEqual(hist.nouveau_statut, 'BROUILLON')

    def test_date_echeance_auto_calculee(self):
        resp = self._create_facture()
        facture = Facture.objects.get(pk=resp.data['id'])
        expected = facture.date_emission + timedelta(days=30)
        self.assertEqual(facture.date_echeance, expected)

    def test_date_echeance_fournie_respectee(self):
        custom_date = (date.today() + timedelta(days=60)).isoformat()
        resp = self._create_facture(date_echeance=custom_date)
        facture = Facture.objects.get(pk=resp.data['id'])
        self.assertEqual(facture.date_echeance, date.today() + timedelta(days=60))

    def test_list_factures_filtre_par_utilisateur(self):
        self._create_facture()
        other_user = User.objects.create_user(
            username='other', email='other@test.com', password='pass123'
        )
        UserConfiguration.objects.create(user=other_user)
        other_client = Client.objects.create(
            utilisateur=other_user, raison_sociale='Autre Client'
        )
        other_api = APIClient()
        other_api.force_authenticate(user=other_user)
        other_api.post('/api/invoices/', {
            'client_id': other_client.pk,
            'objet': 'Autre facture',
            'lignes': [self._ligne_data()],
        }, format='json')

        resp = self.api.get('/api/invoices/')
        self.assertEqual(resp.data['count'], 1)

    def test_update_brouillon_ok(self):
        resp = self._create_facture()
        facture_id = resp.data['id']
        resp2 = self.api.patch(
            f'/api/invoices/{facture_id}/',
            {'objet': 'Modifié', 'lignes': [self._ligne_data()]},
            format='json',
        )
        self.assertEqual(resp2.status_code, status.HTTP_200_OK)
        self.assertEqual(resp2.data['objet'], 'Modifié')

    def test_update_non_brouillon_interdit(self):
        resp = self._create_facture()
        facture_id = resp.data['id']
        self.api.post(
            f'/api/invoices/{facture_id}/changer_statut/',
            {'statut': 'ENVOYEE'},
            format='json',
        )
        resp2 = self.api.patch(
            f'/api/invoices/{facture_id}/',
            {'objet': 'Modifié', 'lignes': [self._ligne_data()]},
            format='json',
        )
        self.assertEqual(resp2.status_code, status.HTTP_400_BAD_REQUEST)

    def test_delete_brouillon_ok(self):
        resp = self._create_facture()
        facture_id = resp.data['id']
        resp2 = self.api.delete(f'/api/invoices/{facture_id}/')
        self.assertEqual(resp2.status_code, status.HTTP_204_NO_CONTENT)

    def test_delete_non_brouillon_interdit(self):
        resp = self._create_facture()
        facture_id = resp.data['id']
        self.api.post(
            f'/api/invoices/{facture_id}/changer_statut/',
            {'statut': 'ENVOYEE'},
            format='json',
        )
        resp2 = self.api.delete(f'/api/invoices/{facture_id}/')
        self.assertEqual(resp2.status_code, status.HTTP_403_FORBIDDEN)

    def test_client_non_modifiable_en_update(self):
        other_client = Client.objects.create(
            utilisateur=self.user, raison_sociale='Autre Client'
        )
        resp = self._create_facture()
        facture_id = resp.data['id']
        resp2 = self.api.patch(
            f'/api/invoices/{facture_id}/',
            {'client_id': other_client.pk, 'lignes': [self._ligne_data()]},
            format='json',
        )
        self.assertEqual(resp2.status_code, status.HTTP_200_OK)
        facture = Facture.objects.get(pk=facture_id)
        self.assertEqual(facture.client_id, self.client_obj.pk)

    def test_unauthenticated_access_denied(self):
        api = APIClient()
        resp = api.get('/api/invoices/')
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)


# =========================================================================
# CHANGER STATUT
# =========================================================================

class FactureChangerStatutTest(InvoiceTestMixin, TestCase):

    def test_brouillon_vers_envoyee(self):
        resp = self._create_facture()
        facture_id = resp.data['id']
        resp2 = self.api.post(
            f'/api/invoices/{facture_id}/changer_statut/',
            {'statut': 'ENVOYEE'},
            format='json',
        )
        self.assertEqual(resp2.status_code, status.HTTP_200_OK)
        self.assertEqual(resp2.data['statut'], 'ENVOYEE')

    def test_numero_genere_au_passage_envoyee(self):
        resp = self._create_facture()
        facture_id = resp.data['id']
        self.assertIsNone(resp.data['numero'])
        resp2 = self.api.post(
            f'/api/invoices/{facture_id}/changer_statut/',
            {'statut': 'ENVOYEE'},
            format='json',
        )
        year = date.today().year
        self.assertEqual(resp2.data['numero'], f'FAC-{year}-001')

    def test_transition_invalide_brouillon_vers_payee(self):
        resp = self._create_facture()
        facture_id = resp.data['id']
        resp2 = self.api.post(
            f'/api/invoices/{facture_id}/changer_statut/',
            {'statut': 'PAYEE'},
            format='json',
        )
        self.assertEqual(resp2.status_code, status.HTTP_400_BAD_REQUEST)

    def test_envoyee_vers_payee(self):
        resp = self._create_facture()
        facture_id = resp.data['id']
        self.api.post(f'/api/invoices/{facture_id}/changer_statut/', {'statut': 'ENVOYEE'}, format='json')
        resp2 = self.api.post(
            f'/api/invoices/{facture_id}/changer_statut/',
            {'statut': 'PAYEE'},
            format='json',
        )
        self.assertEqual(resp2.status_code, status.HTTP_200_OK)
        self.assertEqual(resp2.data['statut'], 'PAYEE')

    def test_envoyee_vers_en_retard(self):
        resp = self._create_facture()
        facture_id = resp.data['id']
        self.api.post(f'/api/invoices/{facture_id}/changer_statut/', {'statut': 'ENVOYEE'}, format='json')
        resp2 = self.api.post(
            f'/api/invoices/{facture_id}/changer_statut/',
            {'statut': 'EN_RETARD'},
            format='json',
        )
        self.assertEqual(resp2.status_code, status.HTTP_200_OK)

    def test_en_retard_vers_payee(self):
        resp = self._create_facture()
        facture_id = resp.data['id']
        self.api.post(f'/api/invoices/{facture_id}/changer_statut/', {'statut': 'ENVOYEE'}, format='json')
        self.api.post(f'/api/invoices/{facture_id}/changer_statut/', {'statut': 'EN_RETARD'}, format='json')
        resp2 = self.api.post(
            f'/api/invoices/{facture_id}/changer_statut/',
            {'statut': 'PAYEE'},
            format='json',
        )
        self.assertEqual(resp2.status_code, status.HTTP_200_OK)

    def test_changer_statut_cree_historique(self):
        resp = self._create_facture()
        facture_id = resp.data['id']
        self.api.post(f'/api/invoices/{facture_id}/changer_statut/', {'statut': 'ENVOYEE'}, format='json')
        facture = Facture.objects.get(pk=facture_id)
        hist = facture.historique.order_by('-created_at').first()
        self.assertEqual(hist.ancien_statut, 'BROUILLON')
        self.assertEqual(hist.nouveau_statut, 'ENVOYEE')

    def test_statut_requis(self):
        resp = self._create_facture()
        facture_id = resp.data['id']
        resp2 = self.api.post(
            f'/api/invoices/{facture_id}/changer_statut/',
            {},
            format='json',
        )
        self.assertEqual(resp2.status_code, status.HTTP_400_BAD_REQUEST)


# =========================================================================
# CREATION DEPUIS DEVIS
# =========================================================================

class FactureFromDevisTest(InvoiceTestMixin, TestCase):

    def test_from_devis_accepte(self):
        devis_id = self._create_devis_accepte()
        resp = self.api.post(
            '/api/invoices/from-devis/',
            {'devis_id': devis_id},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data['statut'], 'BROUILLON')
        self.assertEqual(resp.data['devis_origine'], devis_id)

    def test_from_devis_copie_les_lignes(self):
        devis_id = self._create_devis_accepte()
        resp = self.api.post(
            '/api/invoices/from-devis/',
            {'devis_id': devis_id},
            format='json',
        )
        facture = Facture.objects.get(pk=resp.data['id'])
        self.assertEqual(facture.lignes.count(), 1)
        ligne = facture.lignes.first()
        self.assertEqual(ligne.libelle, 'Prestation')
        self.assertEqual(ligne.quantite, Decimal('2.00'))
        self.assertEqual(ligne.prix_unitaire_ht, Decimal('100.00'))

    def test_from_devis_calcule_totaux(self):
        devis_id = self._create_devis_accepte()
        resp = self.api.post(
            '/api/invoices/from-devis/',
            {'devis_id': devis_id},
            format='json',
        )
        facture = Facture.objects.get(pk=resp.data['id'])
        self.assertEqual(facture.total_ht, Decimal('200.00'))
        self.assertEqual(facture.total_ttc, Decimal('240.00'))

    def test_from_devis_envoye_passe_en_accepte(self):
        """Un devis ENVOYE est automatiquement passé en ACCEPTE."""
        resp = self.api.post('/api/quotes/', {
            'client_id': self.client_obj.pk,
            'objet': 'Devis envoye',
            'lignes': [self._ligne_data()],
        }, format='json')
        devis_id = resp.data['id']
        self.api.post(f'/api/quotes/{devis_id}/changer_statut/', {'statut': 'ENVOYE'}, format='json')

        resp2 = self.api.post(
            '/api/invoices/from-devis/',
            {'devis_id': devis_id},
            format='json',
        )
        self.assertEqual(resp2.status_code, status.HTTP_201_CREATED)
        devis = Devis.objects.get(pk=devis_id)
        self.assertEqual(devis.statut, Devis.STATUT_ACCEPTE)

    def test_from_devis_brouillon_interdit(self):
        resp = self.api.post('/api/quotes/', {
            'client_id': self.client_obj.pk,
            'objet': 'Devis brouillon',
            'lignes': [self._ligne_data()],
        }, format='json')
        devis_id = resp.data['id']
        resp2 = self.api.post(
            '/api/invoices/from-devis/',
            {'devis_id': devis_id},
            format='json',
        )
        self.assertEqual(resp2.status_code, status.HTTP_400_BAD_REQUEST)

    def test_from_devis_refuse_interdit(self):
        resp = self.api.post('/api/quotes/', {
            'client_id': self.client_obj.pk,
            'objet': 'Devis refuse',
            'lignes': [self._ligne_data()],
        }, format='json')
        devis_id = resp.data['id']
        self.api.post(f'/api/quotes/{devis_id}/changer_statut/', {'statut': 'REFUSE'}, format='json')
        resp2 = self.api.post(
            '/api/invoices/from-devis/',
            {'devis_id': devis_id},
            format='json',
        )
        self.assertEqual(resp2.status_code, status.HTTP_400_BAD_REQUEST)

    def test_from_devis_doublon_interdit(self):
        devis_id = self._create_devis_accepte()
        self.api.post('/api/invoices/from-devis/', {'devis_id': devis_id}, format='json')
        resp2 = self.api.post(
            '/api/invoices/from-devis/',
            {'devis_id': devis_id},
            format='json',
        )
        self.assertEqual(resp2.status_code, status.HTTP_400_BAD_REQUEST)

    def test_from_devis_inexistant(self):
        resp = self.api.post(
            '/api/invoices/from-devis/',
            {'devis_id': 99999},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
