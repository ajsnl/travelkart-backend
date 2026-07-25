from .models import Banner, Coupon
from django.db.models import Q

class BannerService:
    @staticmethod
    def get_banner_stats():
        """Compute summary counts for the Banners admin dashboard."""
        total = Banner.objects.count()
        active = Banner.objects.filter(is_active=True).count()
        hero = Banner.objects.filter(display_position='hero').count()
        bottom = Banner.objects.filter(display_position='bottom').count()
        return {
            "total_banners": total,
            "active_banners": active,
            "hero_banners": hero,
            "bottom_banners": bottom
        }

    @staticmethod
    def get_filtered_banners(search=None, status_filter=None, position_filter=None):
        """Fetch and filter banners based on optional search queries and status/position filters."""
        queryset = Banner.objects.all().order_by('-id')
        if search:
            queryset = queryset.filter(title__icontains=search.strip())
        if status_filter == 'active':
            queryset = queryset.filter(is_active=True)
        elif status_filter == 'inactive':
            queryset = queryset.filter(is_active=False)
        if position_filter:
            queryset = queryset.filter(display_position=position_filter.lower())
        return queryset

    @staticmethod
    def get_active_banners(position_filter=None):
        """Fetch active banners ordered by priority_order, filterable by layout position."""
        queryset = Banner.objects.filter(is_active=True).order_by('priority_order', '-id')
        if position_filter:
            queryset = queryset.filter(display_position=position_filter.lower())
        return queryset

class CouponService:
    @staticmethod
    def get_coupon_stats():
        from django.utils import timezone
        from django.db.models import Sum
        from orders.models import Order

        now = timezone.now()
        total_active = Coupon.objects.filter(is_active=True, valid_to__gte=now).count()
        exclude_condition = Q(payment_status='failed') | Q(payment_method='RAZORPAY', payment_status='pending')
        redemptions = Order.objects.exclude(coupon_code__isnull=True).exclude(coupon_code='').exclude(exclude_condition).count()
        revenue_saved = Order.objects.exclude(coupon_code__isnull=True).exclude(coupon_code='').exclude(exclude_condition).aggregate(
            total_saved=Sum('discount')
        )['total_saved'] or 0
        
        # active coupons expiring in the next 7 days
        seven_days_later = now + timezone.timedelta(days=7)
        expiring_soon = Coupon.objects.filter(
            is_active=True, 
            valid_to__gte=now, 
            valid_to__lte=seven_days_later
        ).count()

        return {
            "total_active": total_active,
            "redemptions": redemptions,
            "revenue_saved": float(revenue_saved),
            "expiring_soon": expiring_soon
        }

    @staticmethod
    def get_filtered_coupons(search=None, status_filter=None, type_filter=None):
        from django.utils import timezone

        queryset = Coupon.objects.all().order_by('-id')
        if search:
            queryset = queryset.filter(code__icontains=search.strip())

        now = timezone.now()
        if status_filter == 'active':
            queryset = queryset.filter(is_active=True, valid_to__gte=now)
        elif status_filter == 'expired':
            queryset = queryset.filter(valid_to__lt=now)
        elif status_filter == 'inactive':
            queryset = queryset.filter(is_active=False)

        if type_filter:
            queryset = queryset.filter(discount_type=type_filter.upper())
            
        return queryset

    @staticmethod
    def get_available_coupons(user):
        from django.utils import timezone
        from cart.services import CartService
        from orders.models import Order

        cart = CartService.get_cart(user)
        cart_totals = CartService.get_cart_totals(cart)
        subtotal = float(cart_totals['total_price'])

        now = timezone.now()
        coupons = Coupon.objects.filter(
            is_active=True,
            valid_from__lte=now,
            valid_to__gte=now
        )
        
        available_coupons = []
        for coupon in coupons:
            if coupon.usage_limit is not None and coupon.used_count >= coupon.usage_limit:
                continue
            
            # Check user usage
            has_used = Order.objects.filter(
                user=user, 
                coupon_code=coupon.code
            ).exclude(
                Q(payment_status='failed') | Q(payment_method='RAZORPAY', payment_status='pending')
            ).exists()
            is_eligible = subtotal >= coupon.min_order_amount
            
            available_coupons.append({
                "id": coupon.id,
                "code": coupon.code,
                "discount_type": coupon.discount_type,
                "discount_value": coupon.discount_value,
                "min_order_amount": coupon.min_order_amount,
                "max_discount": coupon.max_discount,
                "valid_to": coupon.valid_to,
                "is_eligible": is_eligible,
                "has_used": has_used,
                "requirement_message": f"Requires minimum purchase of ₹{coupon.min_order_amount:.2f}" if not is_eligible else ""
            })
        return available_coupons

    @staticmethod
    def validate_coupon(user, code):
        from django.utils import timezone
        from rest_framework.exceptions import ValidationError
        from cart.services import CartService
        from orders.models import Order

        code = code.strip().upper()
        if not code:
            raise ValidationError({"error": "Coupon code is required."})

        cart = CartService.get_cart(user)
        cart_totals = CartService.get_cart_totals(cart)
        subtotal = float(cart_totals['total_price'])

        try:
            coupon = Coupon.objects.get(code=code)
        except Coupon.DoesNotExist:
            raise ValidationError({"error": "Invalid coupon code."})

        now = timezone.now()
        if not coupon.is_active or coupon.valid_from > now or coupon.valid_to < now:
            raise ValidationError({"error": "Coupon is expired or inactive."})

        if coupon.usage_limit is not None and coupon.used_count >= coupon.usage_limit:
            raise ValidationError({"error": "Coupon limit has been reached."})

        has_used = Order.objects.filter(
            user=user, 
            coupon_code=coupon.code
        ).exclude(
            Q(payment_status='failed') | Q(payment_method='RAZORPAY', payment_status='pending')
        ).exists()
        if has_used:
            raise ValidationError({"error": "You have already used this coupon."})

        if subtotal < coupon.min_order_amount:
            raise ValidationError({
                "error": f"Minimum purchase of ₹{coupon.min_order_amount:.2f} is required to apply this coupon."
            })

        # Calculate discount
        if coupon.discount_type == 'PERCENT':
            discount = subtotal * (coupon.discount_value / 100.0)
            if coupon.max_discount is not None:
                discount = min(discount, float(coupon.max_discount))
        else:  # FLAT
            discount = float(coupon.discount_value)

        discount = min(discount, subtotal)

        return {
            "valid": True,
            "coupon_code": coupon.code,
            "discount_type": coupon.discount_type,
            "discount_value": coupon.discount_value,
            "discount_amount": round(discount, 2)
        }
