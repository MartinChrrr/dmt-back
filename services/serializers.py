from rest_framework import serializers
from django.apps import apps

class ServicesSerializer(serializers.ModelSerializer):
    class Meta:
        model = apps.get_model('services', 'Prestation')
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']