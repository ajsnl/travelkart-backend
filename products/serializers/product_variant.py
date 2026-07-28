from rest_framework import serializers
from products.models import ProductVariant
from .product_image import ProductImageSerializer

class ProductVariantSerializer(serializers.ModelSerializer):
    images = ProductImageSerializer(many=True, required=False)
    sku = serializers.CharField(validators=[])
    original_price = serializers.ReadOnlyField(source='price')
    offer_price = serializers.SerializerMethodField()
    available_stock = serializers.SerializerMethodField()

    class Meta:
        model = ProductVariant
        fields = [
            'id', 'sku', 'price', 'stock', 'attributes', 'images', 
            'is_active', 'original_price', 'offer_price', 'offer_type', 'offer_value',
            'available_stock'
        ]

    def get_offer_price(self, obj):
        eff = obj.get_effective_offer()
        return eff['offer_price'] if eff['offer_type'] != 'none' else None

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        eff = instance.get_effective_offer()
        if eff['offer_type'] != 'none':
            representation['offer_price'] = eff['offer_price']
            representation['offer_type'] = eff['offer_type']
            representation['offer_value'] = eff['offer_value']
            representation['offer_source'] = eff['source']
        else:
            representation['offer_price'] = None
            representation['offer_type'] = 'none'
            representation['offer_value'] = 0.00
            representation['offer_source'] = 'none'
        return representation

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

    def get_available_stock(self, obj):
        request = self.context.get('request')
        user = request.user if request else None
        
        from cart.models import CartItem
        from django.db.models import Sum
        
        query = CartItem.objects.filter(variant=obj)
        if user and user.is_authenticated:
            query = query.exclude(cart__user=user)
            
        reserved = query.aggregate(total=Sum('quantity'))['total'] or 0
        return max(0, obj.stock - reserved)
