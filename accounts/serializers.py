from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from .models import UserConfiguration

User = get_user_model()


class UserConfigurationSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserConfiguration
        fields = [
            'next_quote_number', 'next_invoice_number',
            'quote_prefix', 'invoice_prefix',
            'payment_deadline_days', 'quote_validity_days'
        ]


class UserSerializer(serializers.ModelSerializer):
    configuration = UserConfigurationSerializer(read_only=True)

    class Meta:
        model = User
        fields = [
            'id', 'email', 'username', 'first_name', 'last_name',
            'company_name', 'siret', 'address', 'postal_code',
            'city', 'phone', 'configuration', 'date_joined'
        ]
        read_only_fields = ['id', 'date_joined']


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True,
        required=True,
        validators=[validate_password]
    )
    password_confirm = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = User
        fields = [
            'email', 'username', 'password', 'password_confirm',
            'first_name', 'last_name', 'company_name', 'siret',
            'address', 'postal_code', 'city', 'phone'
        ]
        extra_kwargs = {
            'first_name': {'required': True},
            'last_name': {'required': True}
        }

    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError(
                {"password": "Les mots de passe ne correspondent pas."}
            )
        return attrs

    def create(self, validated_data):
        validated_data.pop('password_confirm')
        user = User.objects.create_user(**validated_data)
        # Créer la configuration automatiquement
        UserConfiguration.objects.create(user=user)
        return user


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """JWT Token avec infos utilisateur"""
    
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        
        # Ajoute des claims personnalisés au token
        token['email'] = user.email
        token['username'] = user.username
        token['company_name'] = user.company_name
        
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        
        # Ajoute les infos utilisateur dans la réponse
        data['user'] = UserSerializer(self.user).data
        
        return data


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(
        required=True,
        validators=[validate_password]
    )
    new_password_confirm = serializers.CharField(required=True)

    def validate(self, attrs):
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError(
                {"new_password": "Les mots de passe ne correspondent pas."}
            )
        return attrs