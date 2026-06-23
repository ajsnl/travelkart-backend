from django.db import models
from django.conf import settings
from products.models import ProductVariant

class Order(models.Model):
    STATUS_CHOICES = [
        ('processing', 'Processing'),
        ('shipped', 'Shipped'),
        ('out_for_delivery', 'Out for Delivery'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
        ('return_requested', 'Return Requested'),
        ('returned', 'Returned'),
    ]
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='orders')
    tracking_id = models.CharField(max_length=50, unique=True, db_index=True)
    
    # Shipping Address copy (frozen at purchase time)
    full_name = models.CharField(max_length=100)
    phone = models.CharField(max_length=15)
    address_line = models.TextField()
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    pincode = models.CharField(max_length=10)
    country = models.CharField(max_length=50)
    
    # Prices
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    shipping_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Payment & Shipment Status
    payment_method = models.CharField(max_length=20, default='COD')
    payment_status = models.CharField(
        max_length=20, 
        choices=[('pending', 'Pending'), ('paid', 'Paid'), ('failed', 'Failed')], 
        default='pending'
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='processing')
    delivery_estimate = models.CharField(max_length=100, blank=True)
    
    # Order-level cancel/return reason details
    cancel_reason = models.CharField(max_length=100, blank=True, null=True)
    cancel_comments = models.TextField(blank=True, null=True)
    return_reason = models.CharField(max_length=100, blank=True, null=True)
    return_comments = models.TextField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    def __str__(self):
        return f"Order {self.tracking_id} by {self.user.email} ({self.status})"

class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    variant = models.ForeignKey(ProductVariant, on_delete=models.SET_NULL, null=True, blank=True)
    quantity = models.PositiveIntegerField(default=1)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Item-level cancel details
    is_cancelled = models.BooleanField(default=False)
    cancel_reason = models.CharField(max_length=100, blank=True, null=True)
    cancel_comments = models.TextField(blank=True, null=True)
    
    # Item-level return details
    is_returned = models.BooleanField(default=False)
    return_reason = models.CharField(max_length=100, blank=True, null=True)
    return_comments = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.quantity} x {self.variant.sku if self.variant else 'Deleted Item'} (Order {self.order.tracking_id})"