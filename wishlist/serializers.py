from rest_framework import serializers
from .models import Wishlist
from products.serializers import ProductDetailSerializer

class WishlistSerializer(serializers.ModelSerializer):
    product = ProductDetailSerializer(read_only=True)
    product_id = serializers.IntegerField(write_only=True)

    class Meta:
        model = Wishlist
        fields = ['id', 'product', 'product_id', 'added_at']

    def validate_product_id(self, value):
        from products.models import Product
        if not Product.objects.filter(id=value, is_active=True).exists():
            raise serializers.ValidationError("Product does not exist or is inactive.")
        return value

    def create(self, validated_data):
        user = self.context['request'].user
        product_id = validated_data.pop('product_id')
        from products.models import Product
        product = Product.objects.get(id=product_id)
        wishlist_item, created = Wishlist.objects.get_or_create(user=user, product=product)
        return wishlist_item
