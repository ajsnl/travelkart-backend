from django.db.models import Min, Q
from rest_framework.exceptions import ValidationError, NotFound
from .models import Wishlist
from products.models import Product

class WishlistService:
    @staticmethod
    def get_wishlist_queryset(user, ordering=None):
        """Retrieves and orders the user's wishlist items."""
        queryset = Wishlist.objects.filter(user=user).select_related(
            'product__category__parent'
        ).prefetch_related(
            'product__variants__images', 'product__images'
        ).order_by('-added_at')

        if ordering:
            if ordering == 'price_asc' or ordering == 'price_desc':
                from products.models import ProductVariant
                effective_price_expr = ProductVariant.get_effective_price_expression(prefix='product__variants__')
                queryset = queryset.annotate(
                    min_price=Min(effective_price_expr, filter=Q(product__variants__is_active=True))
                )
                if ordering == 'price_asc':
                    queryset = queryset.order_by('min_price')
                else:
                    queryset = queryset.order_by('-min_price')
            elif ordering == 'name_asc':
                queryset = queryset.order_by('product__name')
            elif ordering == 'name_desc':
                queryset = queryset.order_by('-product__name')
            elif ordering == 'oldest':
                queryset = queryset.order_by('added_at')
            elif ordering == 'recently_added':
                queryset = queryset.order_by('-added_at')

        return queryset

    @staticmethod
    def toggle_wishlist_item(user, product_id):
        """Toggles a product's presence in the user's wishlist."""
        if not product_id:
            raise ValidationError({"error": "product_id is required"})

        try:
            # First try matching by standard ID
            product = Product.objects.get(id=product_id, is_active=True)
        except (Product.DoesNotExist, ValueError):
            # If product_id is not integer or not found, try slug fallback
            try:
                product = Product.objects.get(slug=product_id, is_active=True)
            except Product.DoesNotExist:
                raise NotFound({"error": "Product does not exist or is inactive"})

        wishlist_item = Wishlist.objects.filter(user=user, product=product)
        if wishlist_item.exists():
            wishlist_item.delete()
            return {"message": "Removed from wishlist", "in_wishlist": False, "created": False}
        else:
            Wishlist.objects.create(user=user, product=product)
            return {"message": "Added to wishlist", "in_wishlist": True, "created": True}
