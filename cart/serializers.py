from rest_framework import serializers
from .models import Cart, CartItem
from products.models import ProductVariant

class SimpleVariantSerializer(serializers.ModelSerializer):
    product_name = serializers.ReadOnlyField(source='product.name')
    product_id = serializers.ReadOnlyField(source='product.id')
    product_slug = serializers.ReadOnlyField(source='product.slug')
    product_brand = serializers.ReadOnlyField(source='product.brand')
    
    is_product_active = serializers.ReadOnlyField(source='product.is_active')
    is_category_active = serializers.SerializerMethodField()
    offer_price = serializers.SerializerMethodField()
    image_url = serializers.SerializerMethodField()
    available_stock = serializers.SerializerMethodField()

    class Meta:
        model = ProductVariant
        fields = [
            'id', 'sku', 'price', 'stock', 'attributes', 'is_active',
            'product_name', 'product_id', 'product_slug', 'product_brand',
            'is_product_active', 'is_category_active', 'offer_price',
            'offer_type', 'offer_value', 'image_url', 'available_stock'
        ]

    def get_is_category_active(self, obj):
        if not obj.product or not obj.product.category or not obj.product.category.is_active or obj.product.category.is_deleted:
            return False
        if obj.product.category.parent and (not obj.product.category.parent.is_active or obj.product.category.parent.is_deleted):
            return False
        return True

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
        

    def get_image_url(self, obj):
        # Prefer variant's primary or first image
        var_image = obj.images.filter(is_primary=True).first() or obj.images.first()
        if var_image:
            return var_image.image_url
        # Fallback to product general primary or first image
        prod_image = obj.product.images.filter(variant__isnull=True, is_primary=True).first() or obj.product.images.filter(variant__isnull=True).first()
        if prod_image:
            return prod_image.image_url
        return "https://images.unsplash.com/photo-1544816155-12df9643f363?w=800&auto=format&fit=crop&q=80"

    def get_available_stock(self, obj):
        request = self.context.get('request')
        user = request.user if request else None
        exclude_cart = getattr(user, 'cart', None) if user and user.is_authenticated else None
        
        from cart.services import CartService
        return CartService.get_available_stock(obj, exclude_cart=exclude_cart)


class CartItemSerializer(serializers.ModelSerializer):
    variant = SimpleVariantSerializer(read_only=True)
    variant_id = serializers.IntegerField(write_only=True)
    subtotal = serializers.SerializerMethodField()
    discount_amount = serializers.SerializerMethodField()
    

    class Meta:
        model = CartItem
        fields = ['id', 'variant', 'variant_id', 'quantity', 'subtotal','updated_at' ,'discount_amount']

    def get_subtotal(self, obj):
        from cart.services import CartService
        return CartService.get_item_subtotal(obj)

    def get_discount_amount(self, obj):
        from cart.services import CartService
        return CartService.get_item_discount_amount(obj)

    def validate_variant_id(self, value):
        try:
            variant = ProductVariant.objects.get(id=value)
        except ProductVariant.DoesNotExist:
            raise serializers.ValidationError("Variant does not exist.")
        return value

    def validate(self, data):
        variant_id = data.get('variant_id')
        if variant_id:
            try:
                variant = ProductVariant.objects.get(id=variant_id)
            except ProductVariant.DoesNotExist:
                raise serializers.ValidationError("Variant does not exist.")
        else:
            variant = self.instance.variant

        quantity = data.get('quantity')
        if quantity is None and self.instance:
            quantity = self.instance.quantity

        # Enforce maximum quantity limits (10 items)
        if quantity > 10:
            raise serializers.ValidationError({"quantity": "Maximum limit of 10 items reached for this product variant."})

        # Validate blocked/unlisted variant/product/category
        if not variant.is_active:
            raise serializers.ValidationError("This variant is unlisted or inactive.")
        if not variant.product.is_active:
            raise serializers.ValidationError("This product is unlisted or inactive.")
        
        category = variant.product.category
        if not category.is_active or category.is_deleted:
            raise serializers.ValidationError("The category for this product is inactive or deleted.")
        if category.parent and (not category.parent.is_active or category.parent.is_deleted):
            raise serializers.ValidationError("The parent category for this product is inactive or deleted.")

        # Enforce available stock limits
        request = self.context.get('request')
        user = request.user if request else None
        exclude_cart = getattr(user, 'cart', None) if user and user.is_authenticated else None
        if not exclude_cart and self.instance:
            exclude_cart = self.instance.cart
            
        from cart.services import CartService
        available_stock = CartService.get_available_stock(variant, exclude_cart=exclude_cart)
        if available_stock <= 0:
            raise serializers.ValidationError({"quantity": "This item is out of stock."})
        if quantity > available_stock:
            raise serializers.ValidationError({"quantity": f"Only {available_stock} item(s) available in stock."})

        return data


class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)
    total_items = serializers.SerializerMethodField()
    total_price = serializers.SerializerMethodField()
    discount_total = serializers.SerializerMethodField()
    is_checkout_restricted = serializers.SerializerMethodField()

    class Meta:
        model = Cart
        fields = ['id', 'items', 'total_items', 'total_price', 'discount_total', 'is_checkout_restricted']

    def get_total_items(self, obj):
        from cart.services import CartService
        return CartService.get_cart_totals(obj)['total_items']

    def get_total_price(self, obj):
        from cart.services import CartService
        return CartService.get_cart_totals(obj)['total_price']

    def get_discount_total(self, obj):
        from cart.services import CartService
        return CartService.get_cart_totals(obj)['discount_total']

    def get_is_checkout_restricted(self, obj):
        from cart.services import CartService
        return CartService.check_checkout_restricted(obj)
