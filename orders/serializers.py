from rest_framework import serializers
from .models import Order, OrderItem
from cart.serializers import SimpleVariantSerializer

class OrderItemSerializer(serializers.ModelSerializer):
    variant = SimpleVariantSerializer(read_only=True)
    class Meta:
        model = OrderItem
        fields = [
            'id', 'variant', 'quantity', 'price', 
            'is_cancelled', 'cancel_reason', 'cancel_comments',
            'is_returned', 'is_return_requested', 'return_reason', 'return_comments'
        ]

class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    user_email = serializers.ReadOnlyField(source='user.email')
    razorpay_key_id = serializers.SerializerMethodField()
    
    def get_razorpay_key_id(self, obj):
        from django.conf import settings
        return getattr(settings, 'RAZORPAY_KEY_ID', 'rzp_test_dummy_key_id')

    class Meta:
        model = Order
        fields = [
            'id', 'tracking_id', 'user_email', 'full_name', 'phone', 
            'address_line', 'city', 'state', 'pincode', 'country',
            'subtotal', 'shipping_fee', 'discount', 'total_price',
            'payment_method', 'payment_status', 'status', 
            'delivery_estimate', 'created_at', 'updated_at', 'items',
            'cancel_reason', 'cancel_comments', 'return_reason', 'return_comments',
            'razorpay_order_id', 'razorpay_payment_id', 'razorpay_signature',
            'razorpay_key_id'
        ]