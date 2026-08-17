from rest_framework.exceptions import ValidationError, NotFound
from .models import Cart, CartItem
from products.models import ProductVariant
from wishlist.models import Wishlist
from decimal import Decimal


class CartService:
    @staticmethod
    def get_cart(user):
        cart, _ = Cart.objects.get_or_create(user=user)
        return cart

    @classmethod
    def add_item_to_cart(cls, user, variant_id, quantity, request=None):
        """Adds a variant to the user's cart, validating quantity limits, and deletes from wishlist."""
        try:
            quantity = int(quantity)
            if quantity <= 0:
                raise ValidationError({"error": "Quantity must be greater than 0"})
        except (ValueError, TypeError):
            raise ValidationError({"error": "Invalid quantity"})

        if not variant_id:
            raise ValidationError({"error": "variant_id is required"})

        try:
            variant = ProductVariant.objects.get(id=variant_id)
        except ProductVariant.DoesNotExist:
            raise NotFound({"error": "Variant does not exist"})

        cart = cls.get_cart(user)
        cart_item = CartItem.objects.filter(cart=cart, variant=variant).first()

        target_quantity = quantity
        if cart_item:
            target_quantity += cart_item.quantity

        if target_quantity > 10:
            raise ValidationError({"error": "Maximum limit of 10 items reached for this product variant."})

        # Run serializer validation (if needed for stock etc.)
        from .serializers import CartItemSerializer
        serializer = CartItemSerializer(
            instance=cart_item,
            data={"variant_id": variant.id, "quantity": target_quantity},
            partial=True,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)

        if cart_item:
            cart_item.quantity = target_quantity
            cart_item.save()
        else:
            CartItem.objects.create(cart=cart, variant=variant, quantity=target_quantity)

        return cart

    @classmethod
    def update_item_quantity(cls, user, variant_id, quantity, request=None):
        """Updates the quantity of a variant in the user's cart."""
        try:
            quantity = int(quantity)
            if quantity <= 0:
                raise ValidationError({"error": "Quantity must be greater than 0"})
        except (ValueError, TypeError):
            raise ValidationError({"error": "Invalid quantity"})

        if not variant_id:
            raise ValidationError({"error": "variant_id is required"})

        cart = cls.get_cart(user)
        cart_item = CartItem.objects.filter(cart=cart, variant_id=variant_id).first()
        if not cart_item:
            raise NotFound({"error": "Item not in cart"})

        if quantity > 10:
            raise ValidationError({"error": "Maximum limit of 10 items reached for this product variant."})

        from .serializers import CartItemSerializer
        serializer = CartItemSerializer(
            instance=cart_item,
            data={"variant_id": variant_id, "quantity": quantity},
            partial=True,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)

        cart_item.quantity = quantity
        cart_item.save()
        return cart

    @classmethod
    def remove_item_from_cart(cls, user, variant_id):
        """Removes a variant from the user's cart."""
        if not variant_id:
            raise ValidationError({"error": "variant_id is required"})

        cart = cls.get_cart(user)
        CartItem.objects.filter(cart=cart, variant_id=variant_id).delete()
        return cart

    @classmethod
    def clear_cart(cls, user):
        """Deletes all items in the user's cart."""
        cart = cls.get_cart(user)
        cart.items.all().delete()
        return cart

    @staticmethod
    def get_available_stock(variant, exclude_cart=None):
        """Calculates available stock factoring in other users' reserved quantities."""
        from django.db.models import Sum
        query = CartItem.objects.filter(variant=variant)
        if exclude_cart:
            query = query.exclude(cart=exclude_cart)
        reserved = query.aggregate(total=Sum('quantity'))['total'] or 0
        return max(0, variant.stock - reserved)

    @staticmethod
    def get_item_subtotal(item):
        """Calculates item subtotal after applicable discounts."""
        eff = item.variant.get_effective_offer()
        if eff['offer_type'] != 'none':
            price = eff['offer_price']
        else:
            price = item.variant.price
        return price * item.quantity

    @staticmethod
    def get_item_discount_amount(item):
        """Calculates item total discount amount."""
        eff = item.variant.get_effective_offer()
        if eff['offer_type'] != 'none':
            return eff['discount_amount'] * item.quantity
        return Decimal('0.00')

    @classmethod
    def get_cart_totals(cls, cart):
        """Aggregates total items, total price, and total discount for a cart."""
        items = cart.items.all()
        total_items = sum(item.quantity for item in items)
        total_price = sum(cls.get_item_subtotal(item) for item in items)
        discount_total = sum(cls.get_item_discount_amount(item) for item in items)
        return {
            'total_items': total_items,
            'total_price': total_price,
            'discount_total': discount_total
        }

    @classmethod
    def check_checkout_restricted(cls, cart):
        """Checks if a checkout is restricted due to inactive products/categories or stock issues."""
        items = cart.items.all()
        if not items.exists():
            return True

        for item in items:
            v = item.variant
            if not v.is_active or not v.product.is_active:
                return True
            cat = v.product.category
            if not cat.is_active or cat.is_deleted:
                return True
            if cat.parent and (not cat.parent.is_active or cat.parent.is_deleted):
                return True

            available_stock = cls.get_available_stock(v, exclude_cart=cart)
            if item.quantity > available_stock or available_stock == 0:
                return True
        return False