from rest_framework import serializers
from django.db import transaction
from django.db.models import Max
from products.models import Product, ProductVariant, ProductImage
from .product_image import ProductImageSerializer
from .product_variant import ProductVariantSerializer

class ProductListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for product listings."""
    category_name = serializers.ReadOnlyField(source='category.name')
    primary_image = serializers.SerializerMethodField()
    min_price = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'slug', 'short_description', 'category', 'category_name', 
            'brand', 'is_active', 'is_featured', 'free_delivery', 'est_delivery_time',
            'avg_rating', 'total_ratings_count', 'total_sales', 'primary_image', 'min_price',
            'created_at', 'updated_at'
        ]

    def get_primary_image(self, obj):
        # Retrieve first primary image or fallback to first image
        # Using list() takes advantage of Django's prefetch cache if loaded
        images = list(obj.images.all())
        primary = next((img for img in images if img.is_primary and img.variant_id is None), None)
        if not primary:
            primary = next((img for img in images if img.variant_id is None), None)
        return primary.image_url if primary else None

    def get_min_price(self, obj):
        variants = list(obj.variants.all())
        active_prices = [v.price for v in variants if v.is_active]
        return min(active_prices) if active_prices else None


class ProductDetailSerializer(serializers.ModelSerializer):
    """Detailed read representation serializer."""
    variants = ProductVariantSerializer(many=True, read_only=True)
    images = ProductImageSerializer(many=True, read_only=True)
    category_name = serializers.ReadOnlyField(source='category.name')
    is_best_seller = serializers.SerializerMethodField()
    category_active = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'slug', 'short_description', 'description',
            'category', 'category_name', 'brand', 'is_active', 'is_featured',
            'free_delivery', 'est_delivery_time', 'attributes',
            'avg_rating', 'total_ratings_count', 'variants', 'images',
            'total_sales', 'is_best_seller', 'category_active',
            'created_at', 'updated_at'
        ]

    def get_category_active(self, obj):
        if not obj.category or not obj.category.is_active or obj.category.is_deleted:
            return False
        if obj.category.parent and (not obj.category.parent.is_active or obj.category.parent.is_deleted):
            return False
        return True

    def get_is_best_seller(self, obj):
        if not obj.category_id:
            return False
            
        if 'max_sales_by_category' not in self.context:
            self.context['max_sales_by_category'] = {}
            
        cache = self.context['max_sales_by_category']
        if obj.category_id not in cache:
            max_sales = Product.objects.filter(category_id=obj.category_id, is_active=True).aggregate(Max('total_sales'))['total_sales__max']
            cache[obj.category_id] = max_sales or 0
            
        max_sales = cache[obj.category_id]
        if max_sales > 0:
            return obj.total_sales == max_sales
        return False

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        rep['images'] = [img for img in rep.get('images', []) if img.get('variant') is None]
        return rep


class ProductWriteSerializer(serializers.ModelSerializer):
    """Write-only serializer containing validation, create, and update logic."""
    variants = ProductVariantSerializer(many=True, required=False)
    images = ProductImageSerializer(many=True, required=False)

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'slug', 'short_description', 'description',
            'category', 'brand', 'is_active', 'is_featured',
            'free_delivery', 'est_delivery_time', 'attributes',
            'variants', 'images'
        ]

    def create(self, validated_data):
        variants_data = validated_data.pop('variants', [])
        images_data = validated_data.pop('images', [])
        
        # Check duplicate SKUs in the request payload itself
        payload_skus = [v.get('sku') for v in variants_data if v.get('sku')]
        if len(payload_skus) != len(set(s.lower() for s in payload_skus)):
            raise serializers.ValidationError({"variants": "Duplicate SKUs are not allowed in the variants list."})

        # Check SKU uniqueness across products
        for var_data in variants_data:
            sku = var_data.get('sku')
            if sku and ProductVariant.objects.filter(sku__iexact=sku).exists():
                raise serializers.ValidationError({"variants": f"Variant SKU '{sku}' is already in use by another product."})

        with transaction.atomic():
            product = Product.objects.create(**validated_data)
            
            for img_data in images_data:
                ProductImage.objects.create(product=product, **img_data)
                
            for var_data in variants_data:
                var_images_data = var_data.pop('images', [])
                if len(var_images_data) < 3:
                    var_data['is_active'] = False
                variant = ProductVariant.objects.create(product=product, **var_data)
                
                for img_data in var_images_data:
                    img_data.pop('variant', None)
                    ProductImage.objects.create(product=product, variant=variant, **img_data)
                    
        return product

    def update(self, instance, validated_data):
        variants_data = validated_data.pop('variants', None)
        images_data = validated_data.pop('images', None)
        
        with transaction.atomic():
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            instance.save()
            
            if variants_data is not None:
                raw_variants = self.initial_data.get('variants', [])
                
                payload_skus = [v.get('sku') for v in raw_variants if v.get('sku')]
                if len(payload_skus) != len(set(s.lower() for s in payload_skus if s)):
                    raise serializers.ValidationError({"variants": "Duplicate SKUs are not allowed in the variants list."})

                for idx, var_data in enumerate(variants_data):
                    raw_var = raw_variants[idx] if idx < len(raw_variants) else {}
                    var_id = raw_var.get('id')
                    sku = var_data.get('sku')
                    if sku:
                        qs = ProductVariant.objects.filter(sku__iexact=sku)
                        if var_id:
                            qs = qs.exclude(id=int(var_id))
                        if qs.exists():
                            raise serializers.ValidationError({"variants": f"Variant SKU '{sku}' is already in use by another product."})

                existing_variants = {v.id: v for v in instance.variants.all()}
                kept_variant_ids = []
                
                for idx, var_data in enumerate(variants_data):
                    raw_var = raw_variants[idx] if idx < len(raw_variants) else {}
                    var_id = raw_var.get('id')
                    var_images_data = var_data.pop('images', [])
                    
                    if var_id and int(var_id) in existing_variants:
                        variant = existing_variants[int(var_id)]
                        for k, v in var_data.items():
                            if k != 'id':
                                setattr(variant, k, v)
                        if len(var_images_data) < 3:
                            variant.is_active = False
                        variant.save()
                        kept_variant_ids.append(variant.id)
                    else:
                        var_data.pop('id', None)
                        if len(var_images_data) < 3:
                            var_data['is_active'] = False
                        variant = ProductVariant.objects.create(product=instance, **var_data)
                        kept_variant_ids.append(variant.id)
                    
                    variant.images.all().delete()
                    for img_data in var_images_data:
                        img_data.pop('variant', None)
                        ProductImage.objects.create(product=instance, variant=variant, **img_data)
                
                for vid, variant in existing_variants.items():
                    if vid not in kept_variant_ids:
                        variant.delete()
                        
            if images_data is not None:
                instance.images.filter(variant__isnull=True).delete()
                for img_data in images_data:
                    ProductImage.objects.create(product=instance, **img_data)
                    
        return instance
