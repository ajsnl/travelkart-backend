from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import action
from .serializers import CartSerializer
from accounts.authentication import CookieJWTAuthentication
from .services import CartService

class CartViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = [CookieJWTAuthentication]

    def list(self, request):
        cart = CartService.get_cart(request.user)
        serializer = CartSerializer(cart, context={'request': request})
        return Response(serializer.data)

    def create(self, request):
        variant_id = request.data.get('variant_id')
        quantity = request.data.get('quantity', 1)

        cart = CartService.add_item_to_cart(request.user, variant_id, quantity, request=request)
        serializer = CartSerializer(cart, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], url_path='update-item')
    def update_item(self, request):
        variant_id = request.data.get('variant_id')
        quantity = request.data.get('quantity')

        cart = CartService.update_item_quantity(request.user, variant_id, quantity, request=request)
        serializer = CartSerializer(cart, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], url_path='remove-item')
    def remove_item(self, request):
        variant_id = request.data.get('variant_id')

        cart = CartService.remove_item_from_cart(request.user, variant_id)
        serializer = CartSerializer(cart, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], url_path='clear')
    def clear(self, request):
        cart = CartService.clear_cart(request.user)
        serializer = CartSerializer(cart, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)
