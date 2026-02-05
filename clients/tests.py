# Create your tests here.
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from .models import Client, Adresse

User = get_user_model()


class ClientAPITestCase(TestCase):
    """Tests CRUD pour les routes /api/clients/clients/"""

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

        # Créer un client pour user1
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
        """Un utilisateur authentifié voit ses clients"""
        response = self.api_client.get('/api/clients/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)

    def test_list_clients_unauthenticated(self):
        """Un utilisateur non authentifié reçoit un 401"""
        self.api_client.force_authenticate(user=None)
        response = self.api_client.get('/api/clients/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_clients_isolation(self):
        """Un utilisateur ne voit pas les clients d'un autre"""
        # Créer un client pour user2
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
        """Création d'un client avec adresses imbriquées"""
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

    def test_create_client_sans_adresse(self):
        """Création d'un client sans adresse"""
        data = {
            "raison_sociale": "Client Simple",
        }
        response = self.api_client.post(
            '/api/clients/', data, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['adresses'], [])

    def test_create_client_utilisateur_auto(self):
        """L'utilisateur est automatiquement associé au client"""
        data = {"raison_sociale": "Auto User Test"}
        response = self.api_client.post(
            '/api/clients/', data, format='json'
        )
        client = Client.objects.get(id=response.data['id'])
        self.assertEqual(client.utilisateur, self.user1)

    def test_create_client_raison_sociale_required(self):
        """La raison sociale est obligatoire"""
        response = self.api_client.post(
            '/api/clients/', {}, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('raison_sociale', response.data)

    def test_create_client_doublon_raison_sociale(self):
        """Impossible de créer deux clients avec la même raison sociale"""
        data = {"raison_sociale": "Dupont & Fils SARL"}
        response = self.api_client.post(
            '/api/clients/', data, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # -------------------------
    # TESTS RETRIEVE (GET /clients/{id}/)
    # -------------------------

    def test_retrieve_client(self):
        """Récupérer un client par son id"""
        response = self.api_client.get(
            f'/api/clients/{self.client_obj.id}/'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['raison_sociale'], "Dupont & Fils SARL")

    def test_retrieve_client_autre_utilisateur(self):
        """Impossible de récupérer le client d'un autre utilisateur"""
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
        """Modification complète d'un client"""
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
        """Modification partielle d'un client"""
        response = self.api_client.patch(
            f'/api/clients/{self.client_obj.id}/',
            {"email": "updated@dupont-fils.fr"}, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['email'], "updated@dupont-fils.fr")

    def test_update_remplace_adresses(self):
        """Le PUT avec adresses remplace les adresses existantes"""
        # Créer une adresse existante
        Adresse.objects.create(
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
        """Suppression d'un client"""
        response = self.api_client.delete(
            f'/api/clients/{self.client_obj.id}/'
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Client.objects.filter(id=self.client_obj.id).count(), 0)

    def test_delete_client_autre_utilisateur(self):
        """Impossible de supprimer le client d'un autre utilisateur"""
        client_user2 = Client.objects.create(
            utilisateur=self.user2,
            raison_sociale="Client User2"
        )
        response = self.api_client.delete(
            f'/api/clients/{client_user2.id}/'
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(Client.objects.filter(id=client_user2.id).exists())


class AdresseAPITestCase(TestCase):
    """Tests CRUD pour les routes /api/clients/adresses/"""

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

        self.adresse = Adresse.objects.create(
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

    def test_list_adresses(self):
        """Liste les adresses de l'utilisateur connecté"""
        response = self.api_client.get('/api/adresses/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)

    def test_list_adresses_filtre_client_id(self):
        """Filtre les adresses par client_id"""
        response = self.api_client.get(
            f'/api/adresses/?client_id={self.client_obj.id}'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)

    def test_list_adresses_isolation(self):
        """Un utilisateur ne voit pas les adresses d'un autre"""
        Adresse.objects.create(
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

    def test_create_adresse(self):
        """Création d'une adresse pour son propre client"""
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

    def test_create_adresse_client_autre_utilisateur(self):
        """Impossible de créer une adresse sur le client d'un autre"""
        data = {
            "client": self.client_user2.id,
            "type": "SIEGE",
            "ligne1": "Tentative intrusion",
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

    def test_update_adresse(self):
        """Modification d'une adresse"""
        response = self.api_client.patch(
            f'/api/adresses/{self.adresse.id}/',
            {"ville": "Lyon"}, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['ville'], "Lyon")

    # -------------------------
    # TESTS DELETE
    # -------------------------

    def test_delete_adresse(self):
        """Suppression d'une adresse"""
        response = self.api_client.delete(
            f'/api/adresses/{self.adresse.id}/'
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Adresse.objects.filter(id=self.adresse.id).exists())

    def test_delete_adresse_autre_utilisateur(self):
        """Impossible de supprimer l'adresse d'un autre utilisateur"""
        adresse_user2 = Adresse.objects.create(
            client=self.client_user2,
            type="SIEGE",
            ligne1="Adresse protégée",
            code_postal="75000",
            ville="Paris"
        )
        response = self.api_client.delete(
            f'/api/adresses/{adresse_user2.id}/'
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)