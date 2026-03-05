from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from .models import UserConfiguration

User = get_user_model()


class RegisterTestCase(TestCase):
    """Tests pour POST /api/auth/register/"""

    def setUp(self):
        self.api_client = APIClient()
        self.register_url = '/api/auth/register/'
        self.valid_data = {
            "email": "nouveau@test.com",
            "username": "nouveau",
            "password": "Complexpass123!",
            "password_confirm": "Complexpass123!",
            "first_name": "Jean",
            "last_name": "Dupont",
            "company_name": "Ma Boîte",
            "siret": "12345678901234",
        }

    def test_register_success(self):
        """Inscription réussie retourne 201 + tokens"""
        response = self.api_client.post(
            self.register_url, self.valid_data, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)
        self.assertIn('user', response.data)
        self.assertEqual(response.data['user']['email'], 'nouveau@test.com')

    def test_register_creates_configuration(self):
        """L'inscription crée automatiquement une UserConfiguration"""
        self.api_client.post(
            self.register_url, self.valid_data, format='json'
        )
        user = User.objects.get(email='nouveau@test.com')
        self.assertTrue(
            UserConfiguration.objects.filter(user=user).exists()
        )

    def test_register_password_mismatch(self):
        """Mots de passe différents → 400"""
        data = {**self.valid_data, "password_confirm": "AutrePass123!"}
        response = self.api_client.post(
            self.register_url, data, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_password_too_simple(self):
        """Mot de passe trop simple → 400"""
        data = {
            **self.valid_data,
            "password": "123",
            "password_confirm": "123"
        }
        response = self.api_client.post(
            self.register_url, data, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_email_required(self):
        """Email obligatoire"""
        data = {**self.valid_data}
        del data['email']
        response = self.api_client.post(
            self.register_url, data, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_first_last_name_required(self):
        """Prénom et nom obligatoires"""
        data = {**self.valid_data}
        del data['first_name']
        del data['last_name']
        response = self.api_client.post(
            self.register_url, data, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_duplicate_email(self):
        """Email déjà utilisé → 400"""
        User.objects.create_user(
            username='existant', email='nouveau@test.com',
            password='Testpass123!'
        )
        response = self.api_client.post(
            self.register_url, self.valid_data, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class LoginTestCase(TestCase):
    """Tests pour POST /api/auth/login/"""

    def setUp(self):
        self.api_client = APIClient()
        self.login_url = '/api/auth/login/'
        self.user = User.objects.create_user(
            username='testuser', email='test@test.com',
            password='Testpass123!'
        )

    def test_login_with_email(self):
        """Connexion avec email retourne les tokens"""
        response = self.api_client.post(
            self.login_url,
            {"email": "test@test.com", "password": "Testpass123!"},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)

    def test_login_wrong_password(self):
        """Mauvais mot de passe → 401"""
        response = self.api_client.post(
            self.login_url,
            {"email": "test@test.com", "password": "MauvaisPass!"},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_login_nonexistent_user(self):
        """Utilisateur inexistant → 401"""
        response = self.api_client.post(
            self.login_url,
            {"email": "inexistant@test.com", "password": "Testpass123!"},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class LogoutTestCase(TestCase):
    """Tests pour POST /api/auth/logout/"""

    def setUp(self):
        self.api_client = APIClient()
        self.logout_url = '/api/auth/logout/'
        self.user = User.objects.create_user(
            username='testuser', email='test@test.com',
            password='Testpass123!'
        )
        self.refresh = RefreshToken.for_user(self.user)
        self.api_client.force_authenticate(user=self.user)

    def test_logout_success(self):
        """Déconnexion avec refresh token valide"""
        response = self.api_client.post(
            self.logout_url,
            {"refresh": str(self.refresh)},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_logout_blacklists_token(self):
        """Le refresh token est blacklisté après logout"""
        self.api_client.post(
            self.logout_url,
            {"refresh": str(self.refresh)},
            format='json'
        )
        # Tenter de rafraîchir avec le même token
        self.api_client.force_authenticate(user=None)
        response = self.api_client.post(
            '/api/auth/token/refresh/',
            {"refresh": str(self.refresh)},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logout_unauthenticated(self):
        """Logout sans être connecté → 401"""
        self.api_client.force_authenticate(user=None)
        response = self.api_client.post(
            self.logout_url,
            {"refresh": str(self.refresh)},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class TokenRefreshTestCase(TestCase):
    """Tests pour POST /api/auth/token/refresh/"""

    def setUp(self):
        self.api_client = APIClient()
        self.refresh_url = '/api/auth/token/refresh/'
        self.user = User.objects.create_user(
            username='testuser', email='test@test.com',
            password='Testpass123!'
        )
        self.refresh = RefreshToken.for_user(self.user)

    def test_refresh_token_success(self):
        """Rafraîchissement du token retourne un nouveau access"""
        response = self.api_client.post(
            self.refresh_url,
            {"refresh": str(self.refresh)},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)

    def test_refresh_token_invalid(self):
        """Token invalide → 401"""
        response = self.api_client.post(
            self.refresh_url,
            {"refresh": "token_invalide"},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class CurrentUserTestCase(TestCase):
    """Tests pour GET /api/auth/me/"""

    def setUp(self):
        self.api_client = APIClient()
        self.me_url = '/api/auth/me/'
        self.user = User.objects.create_user(
            username='testuser', email='test@test.com',
            password='Testpass123!', first_name='Jean',
            last_name='Dupont', company_name='Ma Boîte'
        )
        self.api_client.force_authenticate(user=self.user)

    def test_get_current_user(self):
        """Retourne les infos de l'utilisateur connecté"""
        response = self.api_client.get(self.me_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['email'], 'test@test.com')
        self.assertEqual(response.data['first_name'], 'Jean')
        self.assertEqual(response.data['company_name'], 'Ma Boîte')

    def test_get_current_user_unauthenticated(self):
        """Non connecté → 401"""
        self.api_client.force_authenticate(user=None)
        response = self.api_client.get(self.me_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class UserProfileTestCase(TestCase):
    """Tests pour GET/PUT/PATCH /api/auth/profile/"""

    def setUp(self):
        self.api_client = APIClient()
        self.profile_url = '/api/auth/profile/'
        self.user = User.objects.create_user(
            username='testuser', email='test@test.com',
            password='Testpass123!', first_name='Jean',
            last_name='Dupont'
        )
        self.api_client.force_authenticate(user=self.user)

    def test_get_profile(self):
        """GET retourne le profil"""
        response = self.api_client.get(self.profile_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['email'], 'test@test.com')

    def test_patch_profile(self):
        """PATCH modifie partiellement le profil"""
        response = self.api_client.patch(
            self.profile_url,
            {"company_name": "Nouvelle Boîte", "phone": "06 12 34 56 78"},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['company_name'], 'Nouvelle Boîte')
        self.assertEqual(response.data['phone'], '06 12 34 56 78')

    def test_put_profile(self):
        """PUT modifie le profil"""
        response = self.api_client.put(
            self.profile_url,
            {
                "email": "test@test.com",
                "username": "testuser",
                "first_name": "Pierre",
                "last_name": "Martin",
                "company_name": "Autre Boîte",
                "siret": "98765432109876",
                "address": "10 rue de la Paix",
                "postal_code": "38000",
                "city": "Grenoble",
                "phone": "04 76 00 00 00"
            },
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['first_name'], 'Pierre')
        self.assertEqual(response.data['city'], 'Grenoble')

    def test_profile_unauthenticated(self):
        """Non connecté → 401"""
        self.api_client.force_authenticate(user=None)
        response = self.api_client.get(self.profile_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class UserConfigurationTestCase(TestCase):
    """Tests pour GET/PUT/PATCH /api/auth/configuration/"""

    def setUp(self):
        self.api_client = APIClient()
        self.config_url = '/api/auth/configuration/'
        self.user = User.objects.create_user(
            username='testuser', email='test@test.com',
            password='Testpass123!'
        )
        UserConfiguration.objects.create(user=self.user)
        self.api_client.force_authenticate(user=self.user)

    def test_get_configuration(self):
        """GET retourne la configuration avec les valeurs par défaut"""
        response = self.api_client.get(self.config_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['quote_prefix'], 'DEV')
        self.assertEqual(response.data['invoice_prefix'], 'FAC')
        self.assertEqual(response.data['payment_deadline_days'], 30)
        self.assertEqual(response.data['next_quote_number'], 1)

    def test_patch_configuration(self):
        """PATCH modifie partiellement la configuration"""
        response = self.api_client.patch(
            self.config_url,
            {
                "quote_prefix": "D",
                "invoice_prefix": "F",
                "payment_deadline_days": 60
            },
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['quote_prefix'], 'D')
        self.assertEqual(response.data['invoice_prefix'], 'F')
        self.assertEqual(response.data['payment_deadline_days'], 60)

    def test_configuration_isolation(self):
        """Un utilisateur ne peut pas voir la config d'un autre"""
        other_user = User.objects.create_user(
            username='other', email='other@test.com',
            password='Testpass123!'
        )
        UserConfiguration.objects.create(
            user=other_user, quote_prefix='XXX'
        )
        # La config retournée est celle de l'utilisateur connecté
        response = self.api_client.get(self.config_url)
        self.assertEqual(response.data['quote_prefix'], 'DEV')

    def test_configuration_unauthenticated(self):
        """Non connecté → 401"""
        self.api_client.force_authenticate(user=None)
        response = self.api_client.get(self.config_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)