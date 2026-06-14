from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from .serializers import WishlistSerializer
from accounts.authentication import CookieJWTAuthentication
from .services import WishlistService

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
        ordering = self.request.query_params.get('ordering')
        return WishlistService.get_wishlist_queryset(self.request.user, ordering)

    @action(detail=False, methods=['post'], url_path='toggle')
    def toggle_wishlist(self, request):
        product_id = request.data.get('product_id')
        result = WishlistService.toggle_wishlist_item(request.user, product_id)
        
        status_code = status.HTTP_201_CREATED if result.get('created') else status.HTTP_200_OK
        response_data = {
            "message": result["message"],
            "in_wishlist": result["in_wishlist"]
        }
        return Response(response_data, status=status_code)
