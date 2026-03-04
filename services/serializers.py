from rest_framework import serializers
from .models import Prestation

class ServicesSerializer(serializers.ModelSerializer):
    class Meta:
        model = Prestation
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at', 'user']