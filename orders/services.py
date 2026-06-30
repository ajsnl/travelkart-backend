import random
from datetime import datetime, timedelta
from django.db import transaction
from rest_framework.exceptions import ValidationError, NotFound, PermissionDenied
from django.contrib.auth import get_user_model

from accounts.models import Address
from cart.services import CartService
from products.models import ProductVariant
from .models import Order, OrderItem, AdminNotification

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
        
        is_gold = getattr(user, 'is_gold_member', False)
        if is_gold or subtotal > 1000:
            shipping_fee = 0
        else:
            shipping_fee = 99
        total_price = subtotal + shipping_fee
        
        # Generate unique tracking ID
        tracking_id = f"TK-{random.randint(100000, 999999)}"
        while Order.objects.filter(tracking_id=tracking_id).exists():
            tracking_id = f"TK-{random.randint(100000, 999999)}"
            
        delivery_date = datetime.now() + timedelta(days=4)
        delivery_estimate = delivery_date.strftime("%A, %d %B %Y")
        
        with transaction.atomic():
            order_items_to_create = []
            for item in cart_items:
                variant = item.variant
                variant = ProductVariant.objects.select_for_update().get(id=variant.id)
                available_stock = CartService.get_available_stock(variant, exclude_cart=cart)
                if item.quantity > available_stock or variant.stock < item.quantity:
                    raise ValidationError({
                        "error": f"Insufficient stock for {variant.product.name} ({variant.sku}). Only {variant.stock} units available."
                    })
                
                # Only deduct stock immediately if COD
                if payment_method.upper() != 'RAZORPAY':
                    variant.stock -= item.quantity
                    variant.save()
                
                unit_price = CartService.get_item_subtotal(item) / item.quantity
                order_items_to_create.append(OrderItem(
                    variant=variant,
                    quantity=item.quantity,
                    price=unit_price
                ))
            
        razorpay_order_id = None
        if payment_method.upper() == 'RAZORPAY':
            from django.conf import settings
            key_id = getattr(settings, 'RAZORPAY_KEY_ID', None)
            key_secret = getattr(settings, 'RAZORPAY_KEY_SECRET', None)
            
            if not key_id or not key_secret or key_id.startswith('dummy') or key_secret.startswith('dummy'):
                raise ValidationError({
                    "error": "Razorpay payment credentials are not configured on the server. Please contact support."
                })
                
            try:
                import requests
                import base64
                auth_str = f"{key_id}:{key_secret}"
                base64_auth = base64.b64encode(auth_str.encode('ascii')).decode('ascii')
                headers = {
                    "Authorization": f"Basic {base64_auth}",
                    "Content-Type": "application/json"
                }
                payload = {
                    "amount": int(total_price * 100),
                    "currency": "INR",
                    "receipt": tracking_id
                }
                response = requests.post("https://api.razorpay.com/v1/orders", headers=headers, json=payload, timeout=10)
                if response.status_code in [200, 201]:
                    razorpay_order_id = response.json().get('id')
                else:
                    raise ValidationError({
                        "error": f"Razorpay order initialization failed with status {response.status_code}: {response.text}"
                    })
            except requests.RequestException as e:
                raise ValidationError({
                    "error": f"Network error connecting to Razorpay payment gateway: {str(e)}"
                })
            except ValidationError:
                raise
            except Exception as e:
                raise ValidationError({
                    "error": f"An error occurred while setting up Razorpay checkout: {str(e)}"
                })

        with transaction.atomic():
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
                payment_status='pending',
                razorpay_order_id=razorpay_order_id
            )
            
            for order_item in order_items_to_create:
                order_item.order = order
                order_item.save()
                
            # Only clear cart immediately if COD
            if payment_method.upper() != 'RAZORPAY':
                CartService.clear_cart(user)
            
        return order

    @staticmethod
    def simulate_order_status(tracking_id, status, user, reason=None, comments=None):
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
                
        with transaction.atomic():
            if status == 'cancelled' and order.status != 'cancelled':
                for item in order.items.all():
                    if item.variant and not getattr(item, 'is_cancelled', False) and not getattr(item, 'is_returned', False):
                        item.variant.stock += item.quantity
                        item.variant.save()
                        item.is_cancelled = True
                        item.cancel_reason = reason or "Order cancelled"
                        item.cancel_comments = comments
                        item.save()
                order.subtotal = 0
                order.total_price = 0
            elif status == 'returned' and order.status != 'returned':
                for item in order.items.all():
                    if item.variant and not getattr(item, 'is_cancelled', False) and not getattr(item, 'is_returned', False):
                        item.variant.stock += item.quantity
                        item.variant.save()
                        item.is_returned = True
                        item.return_reason = reason or "Order returned"
                        item.return_comments = comments
                        item.save()
                order.subtotal = 0
                order.total_price = 0

            order.status = status
            
            # Save reasons if cancelling or returning
            if status == 'cancelled':
                order.cancel_reason = reason
                order.cancel_comments = comments
            elif status == 'return_requested':
                order.return_reason = reason
                order.return_comments = comments
                AdminNotification.objects.create(
                    message=f"Order {order.tracking_id}: Return request submitted.",
                    tracking_id=order.tracking_id
                )
                
            # If order is delivered, update payment status to paid if payment method is COD
            if status == 'delivered' and order.payment_method == 'COD':
                order.payment_status = 'paid'
            if status in ['cancelled', 'returned'] and order.payment_status == 'paid':
                order.payment_status = 'refunded'
                
            order.save()
        return order

    @staticmethod
    def cancel_order_item(item_id, quantity, reason, comments, user):
        try:
            item = OrderItem.objects.select_related('order').get(id=item_id)
        except OrderItem.DoesNotExist:
            raise NotFound({"error": "Order item not found."})
            
        order = item.order
        role = getattr(user, 'role', 'user')
        is_admin = role == 'admin' or user.is_superuser
        if not is_admin and order.user != user:
            raise PermissionDenied({"error": "You do not have permission to modify this order."})
            
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
                
            if not order.items.filter(is_cancelled=False).exists():
                order.status = 'cancelled'
                if order.payment_status == 'paid':
                    order.payment_status = 'refunded'
            order.save()
            
        return order

    @staticmethod
    def return_order_item(item_id, quantity, reason, comments, user):
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
            if quantity == item.quantity:
                item.is_return_requested = True
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
                    is_return_requested=True,
                    return_reason=reason,
                    return_comments=comments
                )
                
            AdminNotification.objects.create(
                message=f"Order {order.tracking_id}: Return requested for item {item.variant.product.name if item.variant else 'product'}.",
                tracking_id=order.tracking_id
            )
            
        return order

    @staticmethod
    def approve_item_return(item_id, user):
        try:
            item = OrderItem.objects.select_related('order').get(id=item_id)
        except OrderItem.DoesNotExist:
            raise NotFound({"error": "Order item not found."})
            
        if not item.is_return_requested:
            raise ValidationError({"error": "This item does not have a pending return request."})
            
        order = item.order
        role = getattr(user, 'role', 'user')
        is_admin = role == 'admin' or user.is_superuser
        if not is_admin:
            raise PermissionDenied({"error": "Only administrators can approve return requests."})
            
        with transaction.atomic():
            # Update item status
            item.is_returned = True
            item.is_return_requested = False
            item.save()
            
            # Restore stock
            if item.variant:
                item.variant.stock += item.quantity
                item.variant.save()
                
            # Reduce subtotal and total_price
            price_reduction = item.price * item.quantity
            order.subtotal -= price_reduction
            order.total_price -= price_reduction
            if order.subtotal < 0: order.subtotal = 0
            if order.total_price < 0: order.total_price = 0
            
            # Check if all items in order are returned or cancelled
            if not order.items.filter(is_cancelled=False, is_returned=False, is_return_requested=False).exists():
                order.status = 'returned'
                if order.payment_status == 'paid':
                    order.payment_status = 'refunded'
                
            order.save()
            
        return order

    @staticmethod
    def reject_item_return(item_id, user):
        try:
            item = OrderItem.objects.select_related('order').get(id=item_id)
        except OrderItem.DoesNotExist:
            raise NotFound({"error": "Order item not found."})
            
        if not item.is_return_requested:
            raise ValidationError({"error": "This item does not have a pending return request."})
            
        order = item.order
        role = getattr(user, 'role', 'user')
        is_admin = role == 'admin' or user.is_superuser
        if not is_admin:
            raise PermissionDenied({"error": "Only administrators can reject return requests."})
            
        with transaction.atomic():
            # Clear return requested flag
            item.is_return_requested = False
            item.save()
            
        return order

    @staticmethod
    def verify_payment(tracking_id, payment_id, order_id, signature, user):
        try:
            order = Order.objects.get(tracking_id=tracking_id, user=user)
        except Order.DoesNotExist:
            raise NotFound({"error": "Order not found."})
            
        from django.conf import settings
        key_secret = getattr(settings, 'RAZORPAY_KEY_SECRET', None)
        if not key_secret or key_secret == 'dummy_key_secret':
            raise ValidationError({"error": "Razorpay credentials are not configured on the server."})
            
        import hmac
        import hashlib
        
        try:
            msg = f"{order_id}|{payment_id}"
            generated_signature = hmac.new(
                key=key_secret.encode('utf-8'),
                msg=msg.encode('utf-8'),
                digestmod=hashlib.sha256
            ).hexdigest()
            
            if hmac.compare_digest(generated_signature, signature):
                with transaction.atomic():
                    # Deduct stock on successful payment verification
                    for item in order.items.all():
                        variant = item.variant
                        if not variant:
                            continue
                        variant = ProductVariant.objects.select_for_update().get(id=variant.id)
                        if variant.stock < item.quantity:
                            raise ValidationError({
                                "error": f"Insufficient stock for {variant.product.name} ({variant.sku}). Only {variant.stock} units available."
                            })
                        variant.stock -= item.quantity
                        variant.save()
                        
                    order.payment_status = 'paid'
                    order.razorpay_payment_id = payment_id
                    order.razorpay_order_id = order_id
                    order.razorpay_signature = signature
                    order.save()
                    
                    CartService.clear_cart(user)
                return True
        except ValidationError:
            raise
        except Exception as e:
            print("Error verifying signature:", e)
            
        order.payment_status = 'failed'
        order.save()
        return False

