from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from decimal import Decimal
from .models import Service

User = get_user_model()


class ServiceAPITestCase(TestCase):
    """CRUD tests for /api/services/ routes"""

    def setUp(self):
        """Base data for each test"""
        self.api_client = APIClient()

        # Create 2 users
        self.user1 = User.objects.create_user(
            username='user1', email='user1@test.com', password='testpass123'
        )
        self.user2 = User.objects.create_user(
            username='user2', email='user2@test.com', password='testpass123'
        )

        # Authenticate user1
        self.api_client.force_authenticate(user=self.user1)

        # Create a service for user1
        self.service = Service.objects.create(
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

    def test_list_services_authenticated(self):
        """An authenticated user sees their services"""
        response = self.api_client.get('/api/services/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'success')
        self.assertEqual(response.data['data']['count'], 1)

    def test_list_services_unauthenticated(self):
        """An unauthenticated user receives a 401"""
        self.api_client.force_authenticate(user=None)
        response = self.api_client.get('/api/services/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data['status'], 'fail')

    def test_list_services_isolation(self):
        """A user does not see another user's services"""
        Service.objects.create(
            utilisateur=self.user2,
            label="Service user2",
            unit_price_excl_tax=Decimal("100.00"),
            unit="heure",
            taux_tva=Decimal("20.00"),
        )
        response = self.api_client.get('/api/services/')
        self.assertEqual(response.data['data']['count'], 1)
        self.assertEqual(
            response.data['data']['results'][0]['label'],
            "Développement web"
        )

    # -------------------------
    # TESTS CREATE (POST /services/)
    # -------------------------

    def test_create_service(self):
        """Create a service"""
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
        self.assertEqual(response.data['status'], 'success')
        self.assertEqual(response.data['data']['label'], "Consulting")

    def test_create_service_user_auto(self):
        """The user is automatically associated with the service"""
        data = {
            "label": "Design UX",
            "unit_price_excl_tax": "500.00",
            "unit": "jour",
            "taux_tva": "20.00",
        }
        response = self.api_client.post(
            '/api/services/', data, format='json'
        )
        service = Service.objects.get(id=response.data['data']['id'])
        self.assertEqual(service.utilisateur, self.user1)

    def test_create_service_label_required(self):
        """Label is required"""
        data = {
            "unit_price_excl_tax": "100.00",
            "unit": "heure",
            "taux_tva": "20.00",
        }
        response = self.api_client.post(
            '/api/services/', data, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['status'], 'fail')
        self.assertIn('label', response.data['data'])

    def test_create_service_unit_price_required(self):
        """Unit price excl. tax is required"""
        data = {
            "label": "Test",
            "unit": "heure",
            "taux_tva": "20.00",
        }
        response = self.api_client.post(
            '/api/services/', data, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['status'], 'fail')
        self.assertIn('unit_price_excl_tax', response.data['data'])

    def test_create_service_unit_invalid(self):
        """An invalid unit is rejected"""
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
        self.assertEqual(response.data['status'], 'fail')
        self.assertIn('unit', response.data['data'])

    def test_create_service_vat_invalid(self):
        """An invalid VAT rate is rejected"""
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
        self.assertEqual(response.data['status'], 'fail')
        self.assertIn('taux_tva', response.data['data'])

    def test_create_service_without_description(self):
        """Create a service without description (optional field)"""
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
        self.assertEqual(response.data['status'], 'success')
        self.assertEqual(response.data['data']['description'], "")

    # -------------------------
    # TESTS RETRIEVE (GET /services/{id}/)
    # -------------------------

    def test_retrieve_service(self):
        """Retrieve a service by its id"""
        response = self.api_client.get(
            f'/api/services/{self.service.id}/'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'success')
        self.assertEqual(response.data['data']['label'], "Développement web")

    def test_retrieve_service_other_user(self):
        """Cannot retrieve another user's service"""
        service_user2 = Service.objects.create(
            utilisateur=self.user2,
            label="Secret service",
            unit_price_excl_tax=Decimal("100.00"),
            unit="heure",
            taux_tva=Decimal("20.00"),
        )
        response = self.api_client.get(
            f'/api/services/{service_user2.id}/'
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data['status'], 'fail')

    # -------------------------
    # TESTS UPDATE (PUT/PATCH /services/{id}/)
    # -------------------------

    def test_update_service(self):
        """Full update of a service"""
        data = {
            "label": "Développement fullstack",
            "description": "React + Django",
            "unit_price_excl_tax": "500.00",
            "unit": "jour",
            "taux_tva": "20.00",
        }
        response = self.api_client.put(
            f'/api/services/{self.service.id}/',
            data, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'success')
        self.assertEqual(response.data['data']['label'], "Développement fullstack")
        self.assertEqual(response.data['data']['unit_price_excl_tax'], "500.00")

    def test_partial_update_service(self):
        """Partial update of a service"""
        response = self.api_client.patch(
            f'/api/services/{self.service.id}/',
            {"unit_price_excl_tax": "550.00"}, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'success')
        self.assertEqual(response.data['data']['unit_price_excl_tax'], "550.00")

    def test_update_service_other_user(self):
        """Cannot update another user's service"""
        service_user2 = Service.objects.create(
            utilisateur=self.user2,
            label="Service user2",
            unit_price_excl_tax=Decimal("100.00"),
            unit="heure",
            taux_tva=Decimal("20.00"),
        )
        response = self.api_client.patch(
            f'/api/services/{service_user2.id}/',
            {"label": "Hacked"}, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data['status'], 'fail')

    # -------------------------
    # TESTS DELETE (DELETE /services/{id}/)
    # -------------------------

    def test_delete_service(self):
        """Delete a service"""
        response = self.api_client.delete(
            f'/api/services/{self.service.id}/'
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(
            Service.objects.filter(id=self.service.id).count(), 0
        )

    def test_delete_service_other_user(self):
        """Cannot delete another user's service"""
        service_user2 = Service.objects.create(
            utilisateur=self.user2,
            label="Protected service",
            unit_price_excl_tax=Decimal("100.00"),
            unit="heure",
            taux_tva=Decimal("20.00"),
        )
        response = self.api_client.delete(
            f'/api/services/{service_user2.id}/'
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(
            Service.objects.filter(id=service_user2.id).exists()
        )
