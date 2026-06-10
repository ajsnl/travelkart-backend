from rest_framework import serializers
from products.models import ProductVariant
from .product_image import ProductImageSerializer

class ProductVariantSerializer(serializers.ModelSerializer):
    images = ProductImageSerializer(many=True, required=False)
    sku = serializers.CharField(validators=[])
    original_price = serializers.ReadOnlyField(source='price')
    offer_price = serializers.SerializerMethodField()

    class Meta:
        model = ProductVariant
        fields = [
            'id', 'sku', 'price', 'stock', 'attributes', 'images', 
            'is_active', 'original_price', 'offer_price', 'offer_type', 'offer_value'
        ]

    def get_offer_price(self, obj):
        if obj.offer_type == 'percentage' and obj.offer_value > 0:
            discount = obj.price * (obj.offer_value / 100)
            return max(0, obj.price - discount)
        elif obj.offer_type == 'flat' and obj.offer_value > 0:
            return max(0, obj.price - obj.offer_value)
        return None

    def validate(self, attrs):
        is_active = attrs.get('is_active', self.instance.is_active if self.instance else False)
        
        images_data = attrs.get('images', None)
        if images_data is not None:
            total_images = len(images_data)
        else:
            total_images = self.instance.images.count() if self.instance else 0
            
        if is_active and total_images < 3:
            raise serializers.ValidationError({
                "is_active": f"A variant must have at least 3 images to be active. Currently has {total_images}."
            })
            
        return attrs
