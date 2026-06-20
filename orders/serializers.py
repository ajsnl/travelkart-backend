from rest_framework import serializers
from .models import Order, OrderItem
from cart.serializers import SimpleVariantSerializer

class OrderItemSerializer(serializers.ModelSerializer):
    variant = SimpleVariantSerializer(read_only=True)
    class Meta:
        model = OrderItem
        fields = ['id', 'variant', 'quantity', 'price']

class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    user_email = serializers.ReadOnlyField(source='user.email')
    class Meta:
        model = Order
        fields = [
            'id', 'tracking_id', 'user_email', 'full_name', 'phone', 
            'address_line', 'city', 'state', 'pincode', 'country',
            'subtotal', 'shipping_fee', 'discount', 'total_price',
            'payment_method', 'payment_status', 'status', 
            'delivery_estimate', 'created_at', 'updated_at', 'items'
        ]