from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from .models import Wishlist
from .serializers import WishlistSerializer
from accounts.authentication import CookieJWTAuthentication

class WishlistPagination(PageNumberPagination):
    page_size = 8
    page_size_query_param = 'page_size'
    max_page_size = 100

class WishlistViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = [CookieJWTAuthentication]
    serializer_class = WishlistSerializer
    pagination_class = WishlistPagination

    def get_queryset(self):
        queryset = Wishlist.objects.filter(user=self.request.user).select_related('product__category__parent').prefetch_related('product__variants__images', 'product__images').order_by('-added_at')
        
        ordering = self.request.query_params.get('ordering')
        if ordering:
            from django.db.models import Min, Q
            if ordering == 'price_asc':
                queryset = queryset.annotate(
                    min_price=Min('product__variants__price', filter=Q(product__variants__is_active=True))
                ).order_by('min_price')
            elif ordering == 'price_desc':
                queryset = queryset.annotate(
                    min_price=Min('product__variants__price', filter=Q(product__variants__is_active=True))
                ).order_by('-min_price')
            elif ordering == 'name_asc':
                queryset = queryset.order_by('product__name')
            elif ordering == 'name_desc':
                queryset = queryset.order_by('-product__name')
            elif ordering == 'oldest':
                queryset = queryset.order_by('added_at')
            elif ordering == 'recently_added':
                queryset = queryset.order_by('-added_at')
        
        return queryset

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'], url_path='toggle')
    def toggle_wishlist(self, request):
        product_id = request.data.get('product_id')
        if not product_id:
            return Response({"error": "product_id is required"}, status=status.HTTP_400_BAD_REQUEST)
        
        from products.models import Product
        try:
            # First try matching by standard ID
            product = Product.objects.get(id=product_id, is_active=True)
        except (Product.DoesNotExist, ValueError):
            # If product_id is not integer or not found, try slug or integer fallback
            try:
                product = Product.objects.get(slug=product_id, is_active=True)
            except Product.DoesNotExist:
                return Response({"error": "Product does not exist or is inactive"}, status=status.HTTP_404_NOT_FOUND)

        wishlist_item = Wishlist.objects.filter(user=request.user, product=product)
        if wishlist_item.exists():
            wishlist_item.delete()
            return Response({"message": "Removed from wishlist", "in_wishlist": False}, status=status.HTTP_200_OK)
        else:
            Wishlist.objects.create(user=request.user, product=product)
            return Response({"message": "Added to wishlist", "in_wishlist": True}, status=status.HTTP_201_CREATED)
