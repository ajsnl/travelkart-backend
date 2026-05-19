from rest_framework import serializers
from accounts.models import User 


class AdminUserSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id',
            'full_name',
            'email',
            'phone',
            'is_active',
            'is_gold_member',
            'date_joined'
        ]

    def get_full_name(self, obj):
        return obj.get_full_name()