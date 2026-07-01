from rest_framework import viewsets, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import action
from django.utils import timezone
from django.db.models import Sum
from .models import Coupon
from .serializers import CouponSerializer
from admin_panel.permissions import IsAdminUserRole
from cart.services import CartService
from orders.models import Order

class AdminCouponViewSet(viewsets.ModelViewSet):
    queryset = Coupon.objects.all().order_by('-id')
    serializer_class = CouponSerializer
    permission_classes = [IsAdminUserRole]

    def get_coupon_stats(self):
        now = timezone.now()
        total_active = Coupon.objects.filter(is_active=True, valid_to__gte=now).count()
        redemptions = Order.objects.exclude(coupon_code__isnull=True).exclude(coupon_code='').count()
        revenue_saved = Order.objects.exclude(coupon_code__isnull=True).exclude(coupon_code='').aggregate(
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

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        
        # Optional search by code
        search = request.query_params.get('search')
        if search:
            queryset = queryset.filter(code__icontains=search.strip())

        # Optional filter by status
        status_filter = request.query_params.get('status')
        now = timezone.now()
        if status_filter == 'active':
            queryset = queryset.filter(is_active=True, valid_to__gte=now)
        elif status_filter == 'expired':
            queryset = queryset.filter(valid_to__lt=now)
        elif status_filter == 'inactive':
            queryset = queryset.filter(is_active=False)

        # Optional filter by type
        type_filter = request.query_params.get('type')
        if type_filter:
            queryset = queryset.filter(discount_type=type_filter.upper())

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            response = self.get_paginated_response(serializer.data)
            response.data['stats'] = self.get_coupon_stats()
            return response
            
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            "results": serializer.data,
            "stats": self.get_coupon_stats()
        })


class UserCouponAvailableListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        cart = CartService.get_cart(request.user)
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
            has_used = Order.objects.filter(user=request.user, coupon_code=coupon.code).exists()
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

        return Response(available_coupons)


class UserCouponValidateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        code = request.data.get('code', '').strip().upper()
        if not code:
            return Response({"error": "Coupon code is required."}, status=400)

        cart = CartService.get_cart(request.user)
        cart_totals = CartService.get_cart_totals(cart)
        subtotal = float(cart_totals['total_price'])

        try:
            coupon = Coupon.objects.get(code=code)
        except Coupon.DoesNotExist:
            return Response({"error": "Invalid coupon code."}, status=400)

        now = timezone.now()
        if not coupon.is_active or coupon.valid_from > now or coupon.valid_to < now:
            return Response({"error": "Coupon is expired or inactive."}, status=400)

        if coupon.usage_limit is not None and coupon.used_count >= coupon.usage_limit:
            return Response({"error": "Coupon limit has been reached."}, status=400)

        # Check user usage
        has_used = Order.objects.filter(user=request.user, coupon_code=coupon.code).exists()
        if has_used:
            return Response({"error": "You have already used this coupon."}, status=400)

        if subtotal < coupon.min_order_amount:
            return Response({
                "error": f"Minimum purchase of ₹{coupon.min_order_amount:.2f} is required to apply this coupon."
            }, status=400)

        # Calculate discount
        if coupon.discount_type == 'PERCENT':
            discount = subtotal * (coupon.discount_value / 100.0)
            if coupon.max_discount is not None:
                discount = min(discount, float(coupon.max_discount))
        else:  # FLAT
            discount = float(coupon.discount_value)

        # Ensure discount does not exceed subtotal
        discount = min(discount, subtotal)

        return Response({
            "valid": True,
            "coupon_code": coupon.code,
            "discount_type": coupon.discount_type,
            "discount_value": coupon.discount_value,
            "discount_amount": round(discount, 2)
        })
