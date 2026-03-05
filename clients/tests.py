from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from .models import Client, Address

User = get_user_model()


class ClientAPITestCase(TestCase):
    """CRUD tests for /api/clients/clients/ routes"""

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

        # Create a client for user1
        self.client_data = {
            "raison_sociale": "Dupont & Fils SARL",
            "siret": "12345678901234",
            "email": "contact@dupont-fils.fr",
            "telephone": "04 76 12 34 56",
            "contact_nom": "Jean Dupont",
            "contact_email": "jean.dupont@dupont-fils.fr",
            "contact_telephone": "06 12 34 56 78",
            "notes": "Client fidèle"
        }

        self.client_obj = Client.objects.create(
            utilisateur=self.user1, **self.client_data
        )

    # -------------------------
    # TESTS LIST (GET /clients/)
    # -------------------------

    def test_list_clients_authenticated(self):
        """An authenticated user sees their clients"""
        response = self.api_client.get('/api/clients/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)

    def test_list_clients_unauthenticated(self):
        """An unauthenticated user receives a 401"""
        self.api_client.force_authenticate(user=None)
        response = self.api_client.get('/api/clients/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_clients_isolation(self):
        """A user does not see another user's clients"""
        Client.objects.create(
            utilisateur=self.user2,
            raison_sociale="Autre Entreprise"
        )
        response = self.api_client.get('/api/clients/')
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(
            response.data['results'][0]['raison_sociale'],
            "Dupont & Fils SARL"
        )

    # -------------------------
    # TESTS CREATE (POST /clients/)
    # -------------------------

    def test_create_client(self):
        """Create a client with nested addresses"""
        data = {
            "raison_sociale": "Nouvelle Entreprise",
            "siret": "98765432109876",
            "email": "contact@nouvelle.fr",
            "telephone": "04 76 00 00 00",
            "adresses": [
                {
                    "type": "SIEGE",
                    "ligne1": "12 rue de la République",
                    "code_postal": "38000",
                    "ville": "Grenoble",
                    "pays": "France"
                }
            ]
        }
        response = self.api_client.post(
            '/api/clients/', data, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['raison_sociale'], "Nouvelle Entreprise")
        self.assertEqual(len(response.data['adresses']), 1)

    def test_create_client_without_address(self):
        """Create a client without address"""
        data = {
            "raison_sociale": "Client Simple",
        }
        response = self.api_client.post(
            '/api/clients/', data, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['adresses'], [])

    def test_create_client_user_auto(self):
        """The user is automatically associated with the client"""
        data = {"raison_sociale": "Auto User Test"}
        response = self.api_client.post(
            '/api/clients/', data, format='json'
        )
        client = Client.objects.get(id=response.data['id'])
        self.assertEqual(client.utilisateur, self.user1)

    def test_create_client_raison_sociale_required(self):
        """Company name is required"""
        response = self.api_client.post(
            '/api/clients/', {}, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('raison_sociale', response.data)

    def test_create_client_duplicate_raison_sociale(self):
        """Cannot create two clients with the same company name"""
        data = {"raison_sociale": "Dupont & Fils SARL"}
        response = self.api_client.post(
            '/api/clients/', data, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # -------------------------
    # TESTS RETRIEVE (GET /clients/{id}/)
    # -------------------------

    def test_retrieve_client(self):
        """Retrieve a client by its id"""
        response = self.api_client.get(
            f'/api/clients/{self.client_obj.id}/'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['raison_sociale'], "Dupont & Fils SARL")

    def test_retrieve_client_other_user(self):
        """Cannot retrieve another user's client"""
        client_user2 = Client.objects.create(
            utilisateur=self.user2,
            raison_sociale="Client User2"
        )
        response = self.api_client.get(
            f'/api/clients/{client_user2.id}/'
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # -------------------------
    # TESTS UPDATE (PUT /clients/{id}/)
    # -------------------------

    def test_update_client(self):
        """Full update of a client"""
        data = {
            "raison_sociale": "Dupont & Fils SAS",
            "siret": "12345678901234",
            "email": "nouveau@dupont-fils.fr",
            "telephone": "04 76 99 99 99",
            "contact_nom": "",
            "contact_email": "",
            "contact_telephone": "",
            "notes": "Passage en SAS"
        }
        response = self.api_client.put(
            f'/api/clients/{self.client_obj.id}/',
            data, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['raison_sociale'], "Dupont & Fils SAS")

    def test_partial_update_client(self):
        """Partial update of a client"""
        response = self.api_client.patch(
            f'/api/clients/{self.client_obj.id}/',
            {"email": "updated@dupont-fils.fr"}, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['email'], "updated@dupont-fils.fr")

    def test_update_replaces_addresses(self):
        """PUT with addresses replaces existing addresses"""
        Address.objects.create(
            client=self.client_obj,
            type="SIEGE",
            ligne1="Ancienne adresse",
            code_postal="38000",
            ville="Grenoble"
        )
        data = {
            "raison_sociale": "Dupont & Fils SARL",
            "adresses": [
                {
                    "type": "FACTURATION",
                    "ligne1": "Nouvelle adresse",
                    "code_postal": "69000",
                    "ville": "Lyon",
                    "pays": "France"
                }
            ]
        }
        response = self.api_client.patch(
            f'/api/clients/{self.client_obj.id}/',
            data, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['adresses']), 1)
        self.assertEqual(response.data['adresses'][0]['ville'], "Lyon")

    # -------------------------
    # TESTS DELETE (DELETE /clients/{id}/)
    # -------------------------

    def test_delete_client(self):
        """Delete a client"""
        response = self.api_client.delete(
            f'/api/clients/{self.client_obj.id}/'
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Client.objects.filter(id=self.client_obj.id).count(), 0)

    def test_delete_client_other_user(self):
        """Cannot delete another user's client"""
        client_user2 = Client.objects.create(
            utilisateur=self.user2,
            raison_sociale="Client User2"
        )
        response = self.api_client.delete(
            f'/api/clients/{client_user2.id}/'
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(Client.objects.filter(id=client_user2.id).exists())


class AddressAPITestCase(TestCase):
    """CRUD tests for /api/clients/adresses/ routes"""

    def setUp(self):
        self.api_client = APIClient()
        self.user1 = User.objects.create_user(
            username='user1', email='user1@test.com', password='testpass123'
        )
        self.user2 = User.objects.create_user(
            username='user2', email='user2@test.com', password='testpass123'
        )
        self.api_client.force_authenticate(user=self.user1)

        self.client_obj = Client.objects.create(
            utilisateur=self.user1,
            raison_sociale="Mon Client"
        )
        self.client_user2 = Client.objects.create(
            utilisateur=self.user2,
            raison_sociale="Client Autre"
        )

        self.address = Address.objects.create(
            client=self.client_obj,
            type="SIEGE",
            ligne1="10 rue Victor Hugo",
            code_postal="38000",
            ville="Grenoble",
            pays="France"
        )

    # -------------------------
    # TESTS LIST
    # -------------------------

    def test_list_addresses(self):
        """List addresses of the connected user"""
        response = self.api_client.get('/api/adresses/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)

    def test_list_addresses_filter_client_id(self):
        """Filter addresses by client_id"""
        response = self.api_client.get(
            f'/api/adresses/?client_id={self.client_obj.id}'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)

    def test_list_addresses_isolation(self):
        """A user does not see another user's addresses"""
        Address.objects.create(
            client=self.client_user2,
            type="SIEGE",
            ligne1="Adresse secrète",
            code_postal="75000",
            ville="Paris"
        )
        response = self.api_client.get('/api/adresses/')
        self.assertEqual(response.data['count'], 1)

    # -------------------------
    # TESTS CREATE
    # -------------------------

    def test_create_address(self):
        """Create an address for own client"""
        data = {
            "client": self.client_obj.id,
            "type": "FACTURATION",
            "ligne1": "5 place Grenette",
            "code_postal": "38000",
            "ville": "Grenoble",
            "pays": "France"
        }
        response = self.api_client.post(
            '/api/adresses/', data, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_create_address_other_user_client(self):
        """Cannot create an address on another user's client"""
        data = {
            "client": self.client_user2.id,
            "type": "SIEGE",
            "ligne1": "Intrusion attempt",
            "code_postal": "75000",
            "ville": "Paris",
            "pays": "France"
        }
        response = self.api_client.post(
            '/api/adresses/', data, format='json'
        )
        self.assertIn(response.status_code, [
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_403_FORBIDDEN
        ])

    # -------------------------
    # TESTS UPDATE
    # -------------------------

    def test_update_address(self):
        """Update an address"""
        response = self.api_client.patch(
            f'/api/adresses/{self.address.id}/',
            {"ville": "Lyon"}, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['ville'], "Lyon")

    # -------------------------
    # TESTS DELETE
    # -------------------------

    def test_delete_address(self):
        """Delete an address"""
        response = self.api_client.delete(
            f'/api/adresses/{self.address.id}/'
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Address.objects.filter(id=self.address.id).exists())

    def test_delete_address_other_user(self):
        """Cannot delete another user's address"""
        address_user2 = Address.objects.create(
            client=self.client_user2,
            type="SIEGE",
            ligne1="Protected address",
            code_postal="75000",
            ville="Paris"
        )
        response = self.api_client.delete(
            f'/api/adresses/{address_user2.id}/'
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
