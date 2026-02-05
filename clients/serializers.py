from rest_framework import serializers
from django.apps import apps


class AdresseSerializer(serializers.ModelSerializer):
    class Meta:
        model = apps.get_model('clients', 'Adresse')
        fields = '__all__'
        read_only_fields = ['id', 'client', 'created_at', 'updated_at']


class ClientSerializer(serializers.ModelSerializer):
    adresses = AdresseSerializer(many=True, required=False)

    class Meta:
        model = apps.get_model('clients', 'Client')
        fields = '__all__'
        read_only_fields = ['utilisateur']

    def create(self, validated_data):
        adresses_data = validated_data.pop('adresses', [])
        client = self.Meta.model.objects.create(**validated_data)
        Adresse = apps.get_model('clients', 'Adresse')
        for adresse_data in adresses_data:
            Adresse.objects.create(client=client, **adresse_data)
        return client

    def update(self, instance, validated_data):
        adresses_data = validated_data.pop('adresses', None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if adresses_data is not None:
            Adresse = apps.get_model('clients', 'Adresse')
            instance.adresses.all().delete()
            for adresse_data in adresses_data:
                Adresse.objects.create(client=instance, **adresse_data)

        return instance