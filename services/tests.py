from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from decimal import Decimal
from .models import Prestation

User = get_user_model()


class PrestationAPITestCase(TestCase):
    """Tests CRUD pour les routes /api/services/"""

    def setUp(self):
        """Données de base pour chaque test"""
        self.api_client = APIClient()

        # Créer 2 utilisateurs
        self.user1 = User.objects.create_user(
            username='user1', email='user1@test.com', password='testpass123'
        )
        self.user2 = User.objects.create_user(
            username='user2', email='user2@test.com', password='testpass123'
        )

        # Authentifier user1
        self.api_client.force_authenticate(user=self.user1)

        # Créer une prestation pour user1
        self.prestation = Prestation.objects.create(
            utilisateur=self.user1,
            label="Développement web",
            description="Développement d'une application React",
            unit_price_excl_tax=Decimal("450.00"),
            unit="jour",
            taux_tva=Decimal("20.00"),
        )

    # -------------------------
    # TESTS LIST (GET /services/)
    # -------------------------

    def test_list_prestations_authenticated(self):
        """Un utilisateur authentifié voit ses prestations"""
        response = self.api_client.get('/api/services/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)

    def test_list_prestations_unauthenticated(self):
        """Un utilisateur non authentifié reçoit un 401"""
        self.api_client.force_authenticate(user=None)
        response = self.api_client.get('/api/services/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_prestations_isolation(self):
        """Un utilisateur ne voit pas les prestations d'un autre"""
        Prestation.objects.create(
            utilisateur=self.user2,
            label="Prestation user2",
            unit_price_excl_tax=Decimal("100.00"),
            unit="heure",
            taux_tva=Decimal("20.00"),
        )
        response = self.api_client.get('/api/services/')
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(
            response.data['results'][0]['label'],
            "Développement web"
        )

    # -------------------------
    # TESTS CREATE (POST /services/)
    # -------------------------

    def test_create_prestation(self):
        """Création d'une prestation"""
        data = {
            "label": "Consulting",
            "description": "Conseil en architecture logicielle",
            "unit_price_excl_tax": "800.00",
            "unit": "jour",
            "taux_tva": "20.00",
        }
        response = self.api_client.post(
            '/api/services/', data, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['label'], "Consulting")

    def test_create_prestation_utilisateur_auto(self):
        """L'utilisateur est automatiquement associé à la prestation"""
        data = {
            "label": "Design UX",
            "unit_price_excl_tax": "500.00",
            "unit": "jour",
            "taux_tva": "20.00",
        }
        response = self.api_client.post(
            '/api/services/', data, format='json'
        )
        prestation = Prestation.objects.get(id=response.data['id'])
        self.assertEqual(prestation.utilisateur, self.user1)

    def test_create_prestation_label_required(self):
        """Le label est obligatoire"""
        data = {
            "unit_price_excl_tax": "100.00",
            "unit": "heure",
            "taux_tva": "20.00",
        }
        response = self.api_client.post(
            '/api/services/', data, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('label', response.data)

    def test_create_prestation_unit_price_required(self):
        """Le prix unitaire HT est obligatoire"""
        data = {
            "label": "Test",
            "unit": "heure",
            "taux_tva": "20.00",
        }
        response = self.api_client.post(
            '/api/services/', data, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('unit_price_excl_tax', response.data)

    def test_create_prestation_unit_invalid(self):
        """Une unité invalide est rejetée"""
        data = {
            "label": "Test",
            "unit_price_excl_tax": "100.00",
            "unit": "semaine",
            "taux_tva": "20.00",
        }
        response = self.api_client.post(
            '/api/services/', data, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('unit', response.data)

    def test_create_prestation_tva_invalid(self):
        """Un taux de TVA invalide est rejeté"""
        data = {
            "label": "Test",
            "unit_price_excl_tax": "100.00",
            "unit": "heure",
            "taux_tva": "15.00",
        }
        response = self.api_client.post(
            '/api/services/', data, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('taux_tva', response.data)

    def test_create_prestation_sans_description(self):
        """Création d'une prestation sans description (champ optionnel)"""
        data = {
            "label": "Maintenance",
            "unit_price_excl_tax": "60.00",
            "unit": "heure",
            "taux_tva": "20.00",
        }
        response = self.api_client.post(
            '/api/services/', data, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['description'], "")

    # -------------------------
    # TESTS RETRIEVE (GET /services/{id}/)
    # -------------------------

    def test_retrieve_prestation(self):
        """Récupérer une prestation par son id"""
        response = self.api_client.get(
            f'/api/services/{self.prestation.id}/'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['label'], "Développement web")

    def test_retrieve_prestation_autre_utilisateur(self):
        """Impossible de récupérer la prestation d'un autre utilisateur"""
        prestation_user2 = Prestation.objects.create(
            utilisateur=self.user2,
            label="Prestation secrète",
            unit_price_excl_tax=Decimal("100.00"),
            unit="heure",
            taux_tva=Decimal("20.00"),
        )
        response = self.api_client.get(
            f'/api/services/{prestation_user2.id}/'
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # -------------------------
    # TESTS UPDATE (PUT/PATCH /services/{id}/)
    # -------------------------

    def test_update_prestation(self):
        """Modification complète d'une prestation"""
        data = {
            "label": "Développement fullstack",
            "description": "React + Django",
            "unit_price_excl_tax": "500.00",
            "unit": "jour",
            "taux_tva": "20.00",
        }
        response = self.api_client.put(
            f'/api/services/{self.prestation.id}/',
            data, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['label'], "Développement fullstack")
        self.assertEqual(response.data['unit_price_excl_tax'], "500.00")

    def test_partial_update_prestation(self):
        """Modification partielle d'une prestation"""
        response = self.api_client.patch(
            f'/api/services/{self.prestation.id}/',
            {"unit_price_excl_tax": "550.00"}, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['unit_price_excl_tax'], "550.00")

    def test_update_prestation_autre_utilisateur(self):
        """Impossible de modifier la prestation d'un autre utilisateur"""
        prestation_user2 = Prestation.objects.create(
            utilisateur=self.user2,
            label="Prestation user2",
            unit_price_excl_tax=Decimal("100.00"),
            unit="heure",
            taux_tva=Decimal("20.00"),
        )
        response = self.api_client.patch(
            f'/api/services/{prestation_user2.id}/',
            {"label": "Hacké"}, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # -------------------------
    # TESTS DELETE (DELETE /services/{id}/)
    # -------------------------

    def test_delete_prestation(self):
        """Suppression d'une prestation"""
        response = self.api_client.delete(
            f'/api/services/{self.prestation.id}/'
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(
            Prestation.objects.filter(id=self.prestation.id).count(), 0
        )

    def test_delete_prestation_autre_utilisateur(self):
        """Impossible de supprimer la prestation d'un autre utilisateur"""
        prestation_user2 = Prestation.objects.create(
            utilisateur=self.user2,
            label="Prestation protégée",
            unit_price_excl_tax=Decimal("100.00"),
            unit="heure",
            taux_tva=Decimal("20.00"),
        )
        response = self.api_client.delete(
            f'/api/services/{prestation_user2.id}/'
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(
            Prestation.objects.filter(id=prestation_user2.id).exists()
        )
