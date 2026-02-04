from rest_framework import serializers
from django.apps import apps


class ClientSerializer(serializers.ModelSerializer):
    class Meta:
        model = apps.get_model('clients', 'Client')
        fields = '__all__'
        read_only_fields = ['utilisateur']


class AdresseSerializer(serializers.ModelSerializer):
    class Meta:
        model = apps.get_model('clients', 'Adresse')
        fields = '__all__'
