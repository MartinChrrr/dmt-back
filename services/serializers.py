from rest_framework import serializers
from .models import Prestation

class PrestationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Prestation
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at', 'utilisateur']
