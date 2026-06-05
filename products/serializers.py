from rest_framework import serializers
from .models import Category, Product, ProductVariant, ProductImage

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = '__all__'


class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = ['id', 'variant', 'image_url', 'is_primary']


class ProductVariantSerializer(serializers.ModelSerializer):
    images = ProductImageSerializer(many=True, required=False)
    sku = serializers.CharField(validators=[])

    class Meta:
        model = ProductVariant
        fields = ['id', 'sku', 'price', 'stock', 'attributes', 'images', 'is_active']

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


class ProductSerializer(serializers.ModelSerializer):
    variants = ProductVariantSerializer(many=True, required=False)
    images = ProductImageSerializer(many=True, required=False) # General product media
    category_name = serializers.ReadOnlyField(source='category.name')

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'slug', 'short_description', 'description',
            'category', 'category_name', 'brand', 'is_active', 'is_featured',
            'free_delivery', 'est_delivery_time', 'attributes',
            'avg_rating', 'total_ratings_count', 'variants', 'images',
            'created_at', 'updated_at'
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
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
            
        instance.save()
        
        if variants_data is not None:
            # Check SKU uniqueness across other products/variants before saving
            raw_variants = self.initial_data.get('variants', [])
            
            # Check duplicate SKUs in the request payload itself
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

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        rep['images'] = [img for img in rep.get('images', []) if img.get('variant') is None]
        
        request = self.context.get('request')
        is_admin = False
        if request and request.user and request.user.is_authenticated:
            if getattr(request.user, 'role', 'user') == 'admin':
                is_admin = True
                
        if not is_admin:
            rep['variants'] = [v for v in rep.get('variants', []) if v.get('is_active', True)]
            
        return rep

