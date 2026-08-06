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
        
        discount_type = data.get('discount_type')
        if not discount_type and self.instance:
            discount_type = self.instance.discount_type
        discount_value = data.get('discount_value')
        if discount_value is None and self.instance:
            discount_value = self.instance.discount_value
        min_order_amount = data.get('min_order_amount')
        if min_order_amount is None and self.instance:
            min_order_amount = self.instance.min_order_amount
        if discount_type == 'FLAT' and discount_value is not None:
            if discount_value <= 0:
                raise serializers.ValidationError({
                    "discount_value": "Flat discount value must be greater than 0."
                })
            if min_order_amount is not None and min_order_amount <= discount_value:
                raise serializers.ValidationError({
                    "min_order_amount": "Minimum purchase requirement must be greater than the discount value."
                })
        elif discount_type == 'PERCENT' and discount_value is not None:
            if discount_value <= 0 or discount_value > 100:
                raise serializers.ValidationError({
                    "discount_value": "Percent discount value must be between 1 and 100."
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
