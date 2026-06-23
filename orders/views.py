from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import NotFound

from .models import Order
from .serializers import OrderSerializer
from .services import OrderService

class OrderCreateListView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """List the current user's order history."""
        orders = Order.objects.filter(user=request.user).order_by('-created_at')
        serializer = OrderSerializer(orders, many=True)
        return Response(serializer.data)
        
    def post(self, request):
        """Place a new order using the user's cart and selected address."""
        address_id = request.data.get('address_id')
        payment_method = request.data.get('payment_method', 'COD')
        order = OrderService.create_order(request.user, address_id, payment_method)
        serializer = OrderSerializer(order)
        return Response(serializer.data, status=201)

class OrderDetailView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get_order(self, tracking_id, user):
        try:
            role = getattr(user, 'role', 'user')
            if role == 'admin' or user.is_superuser:
                return Order.objects.get(tracking_id=tracking_id)
            return Order.objects.get(tracking_id=tracking_id, user=user)
        except Order.DoesNotExist:
            raise NotFound({"error": "Order not found."})
            
    def get(self, request, tracking_id):
        """Retrieve details of a specific order."""
        order = self.get_order(tracking_id, request.user)
        serializer = OrderSerializer(order)
        return Response(serializer.data)

class OrderSimulateStatusView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request, tracking_id):
        """Simulate order status progression."""
        status = request.data.get('status')
        reason = request.data.get('reason')
        comments = request.data.get('comments')
        order = OrderService.simulate_order_status(tracking_id, status, request.user, reason, comments)
        serializer = OrderSerializer(order)
        return Response(serializer.data)

class OrderItemCancelView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request, item_id):
        quantity = request.data.get('quantity')
        reason = request.data.get('reason')
        comments = request.data.get('comments')
        order = OrderService.cancel_order_item(item_id, quantity, reason, comments, request.user)
        serializer = OrderSerializer(order)
        return Response(serializer.data)

class OrderItemReturnView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request, item_id):
        quantity = request.data.get('quantity')
        reason = request.data.get('reason')
        comments = request.data.get('comments')
        order = OrderService.return_order_item(item_id, quantity, reason, comments, request.user)
        serializer = OrderSerializer(order)
        return Response(serializer.data)
