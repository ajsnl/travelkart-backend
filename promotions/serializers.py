from rest_framework import serializers
from .models import Coupon, Banner
from django.utils import timezone

class CouponSerializer(serializers.ModelSerializer):
    class Meta:
        model = Coupon
        fields = [
            'id', 'code', 'discount_type', 'discount_value', 
            'min_order_amount', 'max_discount', 'is_active', 
            'valid_from', 'valid_to', 'usage_limit', 'used_count'
        ]
        read_only_fields = ['id', 'used_count']

    def validate_code(self, value):
        return value.strip().upper()

    def validate(self, data):
        valid_from = data.get('valid_from')
        if not valid_from and self.instance:
            valid_from = self.instance.valid_from
            
        valid_to = data.get('valid_to')
        if not valid_to and self.instance:
            valid_to = self.instance.valid_to

        if valid_from and valid_to and valid_from >= valid_to:
            raise serializers.ValidationError({
                "valid_to": "Expiration date must be after the starting activation date."
            })
            
        return data

class BannerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Banner
        fields = [
            'id', 'title', 'subtitle', 'image', 'is_active', 
            'redirect_url', 'priority_order', 'display_position', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']

    def validate_display_position(self, value):
        valid_positions = ['hero', 'bottom']
        if value not in valid_positions:
            raise serializers.ValidationError(
                f"Invalid position. Must be one of: {', '.join(valid_positions)}"
            )
        return value
