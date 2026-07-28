from rest_framework import serializers
from products.models import Category

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = [
            'id',
            'name',
            'slug',
            'description',
            'parent',
            'is_active',
            'created_at',
            'offer_type',
            'offer_value',
            'max_discount',
            'min_product_price',
            'expiry_date'
        ]
        read_only_fields = ['id']

    def validate_name(self, value):
        qs = Category.objects.filter(is_deleted=False, name__iexact=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("A category with this name already exists (case-insensitive check).")
        return value

    def validate(self, attrs):
        offer_type = attrs.get('offer_type', self.instance.offer_type if self.instance else 'none')
        offer_value = attrs.get('offer_value', self.instance.offer_value if self.instance else 0.00)
        max_discount = attrs.get('max_discount', self.instance.max_discount if self.instance else None)
        min_product_price = attrs.get('min_product_price', self.instance.min_product_price if self.instance else None)
        expiry_date = attrs.get('expiry_date', self.instance.expiry_date if self.instance else None)
        
        if offer_type != 'none':
            if offer_value <= 0:
                raise serializers.ValidationError({"offer_value": "Offer value must be greater than 0 if an offer is active."})
            if offer_type == 'percentage' and offer_value > 100:
                raise serializers.ValidationError({"offer_value": "Percentage offer value cannot be greater than 100%."})
        else:
            # If offer_type is none, reset offer_value
            attrs['offer_value'] = 0.00
        if max_discount is not None and max_discount < 0:
            raise serializers.ValidationError({"max_discount": "Max discount cannot be negative."})
            
        if min_product_price is not None and min_product_price < 0:
            raise serializers.ValidationError({"min_product_price": "Minimum product price cannot be negative."})

        if expiry_date is not None:
            from django.utils import timezone
            if expiry_date <= timezone.now():
                raise serializers.ValidationError({"expiry_date": "Expiration date must be in the future."})
            
        return attrs
