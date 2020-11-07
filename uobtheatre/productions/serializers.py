from rest_framework import serializers
from .models import Production, Society


class SocietySerializer(serializers.ModelSerializer):
    class Meta:
        model = Society 
        fields = '__all__' 


class ProductionSerializer(serializers.ModelSerializer):
    society = SocietySerializer()
    class Meta:
        model = Production 
        fields = '__all__' 
