from rest_framework import serializers
from django.apps import apps

class AdresseNestedSerializer(serializers.ModelSerializer):
    """Serializer pour les adresses imbriquées dans ClientSerializer"""
    class Meta:
        model = apps.get_model('clients', 'Adresse')
        fields = ['id', 'type', 'ligne1', 'ligne2', 'code_postal', 'ville', 'pays', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']
        
class AdresseSerializer(serializers.ModelSerializer):
    class Meta:
        model = apps.get_model('clients', 'Adresse')
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']


class ClientSerializer(serializers.ModelSerializer):
    adresses = AdresseNestedSerializer(many=True, required=False)

    class Meta:
        model = apps.get_model('clients', 'Client')
        fields = '__all__'
        read_only_fields = ['utilisateur']

    def validate_raison_sociale(self, value):
        """Vérifie l'unicité par utilisateur"""
        request = self.context['request']
        queryset = self.Meta.model.objects.filter(
            utilisateur=request.user,
            raison_sociale=value
        )
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise serializers.ValidationError(
                "Vous avez déjà un client avec cette raison sociale."
            )
        return value

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