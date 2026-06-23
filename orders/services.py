import random
from datetime import datetime, timedelta
from django.db import transaction
from rest_framework.exceptions import ValidationError, NotFound, PermissionDenied
from django.contrib.auth import get_user_model

from accounts.models import Address
from cart.services import CartService
from products.models import ProductVariant
from .models import Order, OrderItem

class OrderService:
    @staticmethod
    def create_order(user, address_id, payment_method='COD'):
        """Place a new order using the user's cart and selected address."""
        if not address_id:
            raise ValidationError({"error": "address_id is required."})
            
        try:
            address = Address.objects.get(id=address_id, user=user)
        except Address.DoesNotExist:
            raise ValidationError({"error": "Invalid address selected."})
            
        cart = CartService.get_cart(user)
        cart_items = cart.items.all()
        if not cart_items.exists():
            raise ValidationError({"error": "Your cart is empty. Add items before placing an order."})
            
        if CartService.check_checkout_restricted(cart):
            raise ValidationError({"error": "Some items in your cart are no longer available or out of stock."})
            
        cart_totals = CartService.get_cart_totals(cart)
        subtotal = cart_totals['total_price']
        discount = cart_totals['discount_total']
        
        # Determine shipping fee: Free for gold members OR if order subtotal > 500
        is_gold = getattr(user, 'is_gold_member', False)
        if is_gold or subtotal > 500:
            shipping_fee = 0
        else:
            shipping_fee = 99
        total_price = subtotal + shipping_fee
        
        # Generate unique tracking ID
        tracking_id = f"TK-{random.randint(100000, 999999)}"
        while Order.objects.filter(tracking_id=tracking_id).exists():
            tracking_id = f"TK-{random.randint(100000, 999999)}"
            
        # Compute estimated delivery date (4 days from now)
        delivery_date = datetime.now() + timedelta(days=4)
        delivery_estimate = delivery_date.strftime("%A, %d %B %Y")
        
        with transaction.atomic():
            # Validate and decrement stock
            order_items_to_create = []
            for item in cart_items:
                variant = item.variant
                variant = ProductVariant.objects.select_for_update().get(id=variant.id)
                available_stock = CartService.get_available_stock(variant, exclude_cart=cart)
                if item.quantity > available_stock or variant.stock < item.quantity:
                    raise ValidationError({
                        "error": f"Insufficient stock for {variant.product.name} ({variant.sku}). Only {variant.stock} units available."
                    })
                
                variant.stock -= item.quantity
                variant.save()
                
                unit_price = CartService.get_item_subtotal(item) / item.quantity
                order_items_to_create.append(OrderItem(
                    variant=variant,
                    quantity=item.quantity,
                    price=unit_price
                ))
                
            order = Order.objects.create(
                user=user,
                tracking_id=tracking_id,
                full_name=address.full_name,
                phone=address.phone,
                address_line=address.address_line,
                city=address.city,
                state=address.state,
                pincode=address.pincode,
                country=address.country,
                subtotal=subtotal,
                shipping_fee=shipping_fee,
                discount=discount,
                total_price=total_price,
                payment_method=payment_method,
                delivery_estimate=delivery_estimate,
                status='processing',
                payment_status='pending'
            )
            
            for order_item in order_items_to_create:
                order_item.order = order
                order_item.save()
                
            CartService.clear_cart(user)
            
        return order

    @staticmethod
    def simulate_order_status(tracking_id, status, user, reason=None, comments=None):
        """Simulate advancing/updating order status with lifecycle validations."""
        valid_statuses = [choice[0] for choice in Order.STATUS_CHOICES]
        if not status:
            raise ValidationError({"error": "status field is required."})
        if status not in valid_statuses:
            raise ValidationError({"error": f"Invalid status. Must be one of {valid_statuses}."})
            
        try:
            role = getattr(user, 'role', 'user')
            is_admin = role == 'admin' or user.is_superuser
            if is_admin:
                order = Order.objects.get(tracking_id=tracking_id)
            else:
                order = Order.objects.get(tracking_id=tracking_id, user=user)
        except Order.DoesNotExist:
            raise NotFound({"error": "Order not found."})
            
        # Enforce order cancellation & return rules for non-admin users
        if not is_admin:
            if order.status in ['cancelled', 'returned'] and status != order.status:
                raise ValidationError({"error": f"Cannot change status of a {order.status} order."})
            if status == 'cancelled' and order.status not in ['processing', 'shipped', 'out_for_delivery', 'cancelled']:
                raise ValidationError({"error": "Delivered or returned orders cannot be cancelled."})
            if status == 'returned':
                raise ValidationError({"error": "Users cannot directly set orders as returned. A return request must be submitted."})
            if status == 'return_requested':
                if order.status != 'delivered':
                    raise ValidationError({"error": "Only delivered orders can be returned."})
                import django.utils.timezone as tz
                delta = tz.now() - order.updated_at
                if delta.days > 10:
                    raise ValidationError({"error": "Return window has expired. Returns are only allowed within 10 days of delivery."})
                
        order.status = status
        
        # Save reasons if cancelling or returning
        if status == 'cancelled':
            order.cancel_reason = reason
            order.cancel_comments = comments
        elif status == 'return_requested':
            order.return_reason = reason
            order.return_comments = comments
            
        # If order is delivered, update payment status to paid if payment method is COD
        if status == 'delivered' and order.payment_method == 'COD':
            order.payment_status = 'paid'
            
        order.save()
        return order

    @staticmethod
    def cancel_order_item(item_id, quantity, reason, comments, user):
        """Cancel a quantity of an individual order item during cancel window."""
        try:
            item = OrderItem.objects.select_related('order').get(id=item_id)
        except OrderItem.DoesNotExist:
            raise NotFound({"error": "Order item not found."})
            
        order = item.order
        role = getattr(user, 'role', 'user')
        is_admin = role == 'admin' or user.is_superuser
        if not is_admin and order.user != user:
            raise PermissionDenied({"error": "You do not have permission to modify this order."})
            
        # Check cancel window
        if not is_admin and order.status not in ['processing', 'shipped', 'out_for_delivery']:
            raise ValidationError({"error": "This order is not in the cancellation window."})
            
        if quantity is not None:
            try:
                quantity = int(quantity)
                if quantity <= 0:
                    raise ValueError()
            except ValueError:
                raise ValidationError({"error": "Invalid quantity specified."})
            if quantity > item.quantity:
                raise ValidationError({"error": "Quantity to cancel exceeds ordered quantity."})
        else:
            quantity = item.quantity
            
        with transaction.atomic():
            # Restore stock
            if item.variant:
                item.variant.stock += quantity
                item.variant.save()
                
            # Update price and quantities
            price_reduction = item.price * quantity
            order.subtotal -= price_reduction
            order.total_price -= price_reduction
            if order.subtotal < 0: order.subtotal = 0
            if order.total_price < 0: order.total_price = 0
            
            if quantity == item.quantity:
                item.is_cancelled = True
                item.cancel_reason = reason
                item.cancel_comments = comments
                item.save()
            else:
                item.quantity -= quantity
                item.save()
                OrderItem.objects.create(
                    order=order,
                    variant=item.variant,
                    quantity=quantity,
                    price=item.price,
                    is_cancelled=True,
                    cancel_reason=reason,
                    cancel_comments=comments
                )
                
            # Check if order has any remaining active items
            if not order.items.filter(is_cancelled=False).exists():
                order.status = 'cancelled'
            order.save()
            
        return order

    @staticmethod
    def return_order_item(item_id, quantity, reason, comments, user):
        """Return a quantity of an individual order item post-delivery."""
        try:
            item = OrderItem.objects.select_related('order').get(id=item_id)
        except OrderItem.DoesNotExist:
            raise NotFound({"error": "Order item not found."})
            
        order = item.order
        role = getattr(user, 'role', 'user')
        is_admin = role == 'admin' or user.is_superuser
        if not is_admin and order.user != user:
            raise PermissionDenied({"error": "You do not have permission to modify this order."})
            
        # Check return window
        if not is_admin and order.status != 'delivered':
            raise ValidationError({"error": "Only delivered orders can be returned."})
            
        if quantity is not None:
            try:
                quantity = int(quantity)
                if quantity <= 0:
                    raise ValueError()
            except ValueError:
                raise ValidationError({"error": "Invalid quantity specified."})
            if quantity > item.quantity:
                raise ValidationError({"error": "Quantity to return exceeds purchased quantity."})
        else:
            quantity = item.quantity
            
        with transaction.atomic():
            # Restore stock
            if item.variant:
                item.variant.stock += quantity
                item.variant.save()
                
            # Update price and quantities
            price_reduction = item.price * quantity
            order.subtotal -= price_reduction
            order.total_price -= price_reduction
            if order.subtotal < 0: order.subtotal = 0
            if order.total_price < 0: order.total_price = 0
            
            if quantity == item.quantity:
                item.is_returned = True
                item.return_reason = reason
                item.return_comments = comments
                item.save()
            else:
                item.quantity -= quantity
                item.save()
                OrderItem.objects.create(
                    order=order,
                    variant=item.variant,
                    quantity=quantity,
                    price=item.price,
                    is_returned=True,
                    return_reason=reason,
                    return_comments=comments
                )
                
            # Check if order has any remaining active items
            if not order.items.filter(is_cancelled=False, is_returned=False).exists():
                order.status = 'returned'
            order.save()
            
        return order
