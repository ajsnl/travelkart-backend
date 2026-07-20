from django.db.models import Q, Min
from products.models import Product, Category

class ProductService:
    @staticmethod
    def get_admin_brands():
        return Product.objects.exclude(
            brand__isnull=True
        ).exclude(
            brand=""
        ).values_list('brand', flat=True).distinct().order_by('brand')

    @staticmethod
    def get_user_brands():
        return Product.objects.filter(
            is_active=True
        ).exclude(
            brand__isnull=True
        ).exclude(
            brand=""
        ).values_list('brand', flat=True).distinct().order_by('brand')

    @staticmethod
    def filter_admin_products(queryset, query_params):
        """Filters product queryset for administrative views."""
        category = query_params.get('category')
        brand = query_params.get('brand')
        is_active = query_params.get('is_active')
        is_featured = query_params.get('is_featured')

        if category:
            subcategories = Category.objects.filter(parent_id=category, is_deleted=False)
            subcategory_ids = list(subcategories.values_list('id', flat=True))
            if subcategory_ids:
                queryset = queryset.filter(Q(category_id=category) | Q(category_id__in=subcategory_ids))
            else:
                queryset = queryset.filter(category_id=category)

        if brand:
            queryset = queryset.filter(brand__iexact=brand)

        if is_active is not None:
            is_active_bool = is_active.lower() in ['true', '1']
            queryset = queryset.filter(is_active=is_active_bool)

        if is_featured is not None:
            is_featured_bool = is_featured.lower() in ['true', '1']
            queryset = queryset.filter(is_featured=is_featured_bool)

        return queryset

    @staticmethod
    def filter_user_products(queryset, action, query_params):
        """Filters product queryset for user views, including visibility check, price filter and ordering."""
        #  Apply visibility checks based on action
        if action == 'list':
            queryset = queryset.filter(is_active=True)
            # Only show products in active and non-deleted categories
            queryset = queryset.filter(category__is_active=True, category__is_deleted=False)
            # Exclude products whose parent category is inactive or deleted
            queryset = queryset.exclude(category__parent__is_active=False).exclude(category__parent__is_deleted=True)
            # Prevent product listing before adding at least one variant (active or inactive)
            queryset = queryset.filter(variants__isnull=False).distinct()
        elif action == 'retrieve':
            # Allow viewing but ensure category itself is not deleted
            queryset = queryset.filter(category__is_deleted=False).exclude(category__parent__is_deleted=True)

        category = query_params.get('category')
        brand = query_params.get('brand')
        is_featured = query_params.get('is_featured')

        if category:
            subcategories = Category.objects.filter(parent_id=category, is_active=True, is_deleted=False)
            subcategory_ids = list(subcategories.values_list('id', flat=True))
            if subcategory_ids:
                queryset = queryset.filter(Q(category_id=category) | Q(category_id__in=subcategory_ids))
            else:
                queryset = queryset.filter(category_id=category)

        if brand:
            queryset = queryset.filter(brand__iexact=brand)

        if is_featured is not None:
            is_featured_bool = is_featured.lower() in ['true', '1']
            queryset = queryset.filter(is_featured=is_featured_bool)

        # Price range filter using active variants' effective (offer) price
        min_price = query_params.get('min_price')
        max_price = query_params.get('max_price')
        
        from django.db.models import Case, When, F, DecimalField, Min
        
        effective_price_expr = Case(
            When(variants__offer_type='percentage', variants__offer_value__gt=0,
                 then=F('variants__price') - (F('variants__price') * F('variants__offer_value') / 100.0)),
            When(variants__offer_type='flat', variants__offer_value__gt=0,
                 then=F('variants__price') - F('variants__offer_value')),
            default=F('variants__price'),
            output_field=DecimalField()
        )

        if min_price or max_price:
            from products.models import ProductVariant
            matching_variants = ProductVariant.objects.filter(is_active=True).annotate(
                effective_price=Case(
                    When(offer_type='percentage', offer_value__gt=0,
                         then=F('price') - (F('price') * F('offer_value') / 100.0)),
                    When(offer_type='flat', offer_value__gt=0,
                         then=F('price') - F('offer_value')),
                    default=F('price'),
                    output_field=DecimalField()
                )
            )
            if min_price:
                matching_variants = matching_variants.filter(effective_price__gte=min_price)
            if max_price:
                matching_variants = matching_variants.filter(effective_price__lte=max_price)
            
            matching_product_ids = matching_variants.values_list('product_id', flat=True).distinct()
            queryset = queryset.filter(id__in=matching_product_ids)

        # Sorting
        ordering = query_params.get('ordering')
        if ordering:
            if ordering == 'price_asc' or ordering == 'price_desc':
                queryset = queryset.annotate(
                    min_effective_price=Min(effective_price_expr, filter=Q(variants__is_active=True))
                )
                if ordering == 'price_asc':
                    queryset = queryset.order_by('min_effective_price')
                else:
                    queryset = queryset.order_by('-min_effective_price')
            elif ordering == 'name_asc':
                queryset = queryset.order_by('name')
            elif ordering == 'name_desc':
                queryset = queryset.order_by('-name')

        return queryset
