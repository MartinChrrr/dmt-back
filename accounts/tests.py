from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from .models import UserConfiguration

User = get_user_model()


class RegisterTestCase(TestCase):
    """Tests for POST /api/auth/register/"""

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
        """Successful registration returns 201 + tokens"""
        response = self.api_client.post(
            self.register_url, self.valid_data, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['status'], 'success')
        self.assertIn('access', response.data['data'])
        self.assertIn('refresh', response.data['data'])
        self.assertIn('user', response.data['data'])
        self.assertEqual(response.data['data']['user']['email'], 'nouveau@test.com')

    def test_register_creates_configuration(self):
        """Registration automatically creates a UserConfiguration"""
        self.api_client.post(
            self.register_url, self.valid_data, format='json'
        )
        user = User.objects.get(email='nouveau@test.com')
        self.assertTrue(
            UserConfiguration.objects.filter(user=user).exists()
        )

    def test_register_password_mismatch(self):
        """Different passwords -> 400"""
        data = {**self.valid_data, "password_confirm": "AutrePass123!"}
        response = self.api_client.post(
            self.register_url, data, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['status'], 'fail')

    def test_register_password_too_simple(self):
        """Too simple password -> 400"""
        data = {
            **self.valid_data,
            "password": "123",
            "password_confirm": "123"
        }
        response = self.api_client.post(
            self.register_url, data, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['status'], 'fail')

    def test_register_email_required(self):
        """Email is required"""
        data = {**self.valid_data}
        del data['email']
        response = self.api_client.post(
            self.register_url, data, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['status'], 'fail')

    def test_register_first_last_name_required(self):
        """First name and last name are required"""
        data = {**self.valid_data}
        del data['first_name']
        del data['last_name']
        response = self.api_client.post(
            self.register_url, data, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['status'], 'fail')

    def test_register_duplicate_email(self):
        """Already used email -> 400"""
        User.objects.create_user(
            username='existant', email='nouveau@test.com',
            password='Testpass123!'
        )
        response = self.api_client.post(
            self.register_url, self.valid_data, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['status'], 'fail')


class LoginTestCase(TestCase):
    """Tests for POST /api/auth/login/"""

    def setUp(self):
        self.api_client = APIClient()
        self.login_url = '/api/auth/login/'
        self.user = User.objects.create_user(
            username='testuser', email='test@test.com',
            password='Testpass123!'
        )

    def test_login_with_email(self):
        """Login with email returns tokens"""
        response = self.api_client.post(
            self.login_url,
            {"email": "test@test.com", "password": "Testpass123!"},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'success')
        self.assertIn('access', response.data['data'])
        self.assertIn('refresh', response.data['data'])

    def test_login_wrong_password(self):
        """Wrong password -> 401"""
        response = self.api_client.post(
            self.login_url,
            {"email": "test@test.com", "password": "WrongPass!"},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data['status'], 'fail')

    def test_login_nonexistent_user(self):
        """Nonexistent user -> 401"""
        response = self.api_client.post(
            self.login_url,
            {"email": "nonexistent@test.com", "password": "Testpass123!"},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data['status'], 'fail')


class LogoutTestCase(TestCase):
    """Tests for POST /api/auth/logout/"""

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
        """Logout with valid refresh token"""
        response = self.api_client.post(
            self.logout_url,
            {"refresh": str(self.refresh)},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'success')

    def test_logout_blacklists_token(self):
        """Refresh token is blacklisted after logout"""
        self.api_client.post(
            self.logout_url,
            {"refresh": str(self.refresh)},
            format='json'
        )
        # Try to refresh with the same token
        self.api_client.force_authenticate(user=None)
        response = self.api_client.post(
            '/api/auth/token/refresh/',
            {"refresh": str(self.refresh)},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logout_unauthenticated(self):
        """Logout without being connected -> 401"""
        self.api_client.force_authenticate(user=None)
        response = self.api_client.post(
            self.logout_url,
            {"refresh": str(self.refresh)},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class TokenRefreshTestCase(TestCase):
    """Tests for POST /api/auth/token/refresh/"""

    def setUp(self):
        self.api_client = APIClient()
        self.refresh_url = '/api/auth/token/refresh/'
        self.user = User.objects.create_user(
            username='testuser', email='test@test.com',
            password='Testpass123!'
        )
        self.refresh = RefreshToken.for_user(self.user)

    def test_refresh_token_success(self):
        """Token refresh returns a new access token"""
        response = self.api_client.post(
            self.refresh_url,
            {"refresh": str(self.refresh)},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'success')
        self.assertIn('access', response.data['data'])

    def test_refresh_token_invalid(self):
        """Invalid token -> 401"""
        response = self.api_client.post(
            self.refresh_url,
            {"refresh": "invalid_token"},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data['status'], 'fail')


class CurrentUserTestCase(TestCase):
    """Tests for GET /api/auth/me/"""

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
        """Returns the connected user's info"""
        response = self.api_client.get(self.me_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'success')
        self.assertEqual(response.data['data']['email'], 'test@test.com')
        self.assertEqual(response.data['data']['first_name'], 'Jean')
        self.assertEqual(response.data['data']['company_name'], 'Ma Boîte')

    def test_get_current_user_unauthenticated(self):
        """Not connected -> 401"""
        self.api_client.force_authenticate(user=None)
        response = self.api_client.get(self.me_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data['status'], 'fail')


class UserProfileTestCase(TestCase):
    """Tests for GET/PUT/PATCH /api/auth/profile/"""

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
        """GET returns the profile"""
        response = self.api_client.get(self.profile_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'success')
        self.assertEqual(response.data['data']['email'], 'test@test.com')

    def test_patch_profile(self):
        """PATCH partially updates the profile"""
        response = self.api_client.patch(
            self.profile_url,
            {"company_name": "Nouvelle Boîte", "phone": "06 12 34 56 78"},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'success')
        self.assertEqual(response.data['data']['company_name'], 'Nouvelle Boîte')
        self.assertEqual(response.data['data']['phone'], '06 12 34 56 78')

    def test_put_profile(self):
        """PUT updates the profile"""
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
        self.assertEqual(response.data['status'], 'success')
        self.assertEqual(response.data['data']['first_name'], 'Pierre')
        self.assertEqual(response.data['data']['city'], 'Grenoble')

    def test_profile_unauthenticated(self):
        """Not connected -> 401"""
        self.api_client.force_authenticate(user=None)
        response = self.api_client.get(self.profile_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data['status'], 'fail')


class UserConfigurationTestCase(TestCase):
    """Tests for GET/PUT/PATCH /api/auth/configuration/"""

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
        """GET returns the configuration with default values"""
        response = self.api_client.get(self.config_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'success')
        self.assertEqual(response.data['data']['quote_prefix'], 'DEV')
        self.assertEqual(response.data['data']['invoice_prefix'], 'FAC')
        self.assertEqual(response.data['data']['payment_deadline_days'], 30)
        self.assertEqual(response.data['data']['next_quote_number'], 1)

    def test_patch_configuration(self):
        """PATCH partially updates the configuration"""
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
        self.assertEqual(response.data['status'], 'success')
        self.assertEqual(response.data['data']['quote_prefix'], 'D')
        self.assertEqual(response.data['data']['invoice_prefix'], 'F')
        self.assertEqual(response.data['data']['payment_deadline_days'], 60)

    def test_configuration_isolation(self):
        """A user cannot see another user's config"""
        other_user = User.objects.create_user(
            username='other', email='other@test.com',
            password='Testpass123!'
        )
        UserConfiguration.objects.create(
            user=other_user, quote_prefix='XXX'
        )
        # The returned config is that of the connected user
        response = self.api_client.get(self.config_url)
        self.assertEqual(response.data['data']['quote_prefix'], 'DEV')

    def test_configuration_unauthenticated(self):
        """Not connected -> 401"""
        self.api_client.force_authenticate(user=None)
        response = self.api_client.get(self.config_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data['status'], 'fail')
