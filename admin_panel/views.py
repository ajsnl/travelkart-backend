from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django.db.models import Sum, Q
from django.db import transaction
from .serializers import AdminUserSerializer
from .permissions import IsAdminUserRole
from .services import AdminUserService
from orders.models import Order
from orders.serializers import OrderSerializer


class UserPagination(PageNumberPagination):
    page_size = 10


class OrderPagination(PageNumberPagination):
    page_size = 10


class AdminUserListView(APIView):
    permission_classes = [IsAdminUserRole]

    def get(self, request):
        search = request.GET.get('search')
        is_active = request.GET.get('is_active')
        is_gold = request.GET.get('is_gold')

        users = AdminUserService.get_users_queryset(search, is_active, is_gold)

        paginator = UserPagination()
        paginated_users = paginator.paginate_queryset(users, request)

        serializer = AdminUserSerializer(paginated_users, many=True)
        response = paginator.get_paginated_response(serializer.data)

        stats = AdminUserService.get_user_stats()
        response.data['stats'] = stats

        return response
    


class ToggleUserBlockView(APIView):
    permission_classes = [IsAdminUserRole]

    def patch(self, request, user_id):
        confirm = request.data.get("confirm")
        
        user = AdminUserService.toggle_user_block(request.user, user_id, confirm)

        return Response({
            "message": "User blocked" if not user.is_active else "User unblocked",
            "is_active": user.is_active
        })


class AdminOrderListView(APIView):
    permission_classes = [IsAdminUserRole]

    def get(self, request):
        search = request.GET.get('search')
        status = request.GET.get('status')
        payment_status = request.GET.get('payment_status')

        orders = Order.objects.all().order_by('-created_at')

        if search:
            orders = orders.filter(
                Q(tracking_id__icontains=search) |
                Q(user__email__icontains=search) |
                Q(full_name__icontains=search) |
                Q(city__icontains=search)
            )

        if status:
            orders = orders.filter(status=status)

        if payment_status:
            orders = orders.filter(payment_status=payment_status)

        all_orders = Order.objects.all()
        total_orders = all_orders.count()
        processing_orders = all_orders.filter(status='processing').count()
        completed_orders = all_orders.filter(status='delivered').count()
        cancelled_orders = all_orders.filter(status='cancelled').count()
        
        total_revenue = all_orders.exclude(
            status__in=['cancelled', 'returned']
        ).aggregate(sum=Sum('total_price'))['sum'] or 0.00
        
        stats = {
            "total_orders": total_orders,
            "processing_orders": processing_orders,
            "completed_orders": completed_orders,
            "cancelled_orders": cancelled_orders,
            "total_revenue": float(total_revenue)
        }

        paginator = OrderPagination()
        paginated_orders = paginator.paginate_queryset(orders, request)
        serializer = OrderSerializer(paginated_orders, many=True)
        response = paginator.get_paginated_response(serializer.data)
        response.data['stats'] = stats
        return response


class AdminOrderDetailView(APIView):
    permission_classes = [IsAdminUserRole]

    def get(self, request, tracking_id):
        try:
            order = Order.objects.get(tracking_id=tracking_id)
        except Order.DoesNotExist:
            return Response({"error": "Order not found."}, status=404)
        serializer = OrderSerializer(order)
        return Response(serializer.data)

    def patch(self, request, tracking_id):
        try:
            order = Order.objects.get(tracking_id=tracking_id)
        except Order.DoesNotExist:
            return Response({"error": "Order not found."}, status=404)

        status = request.data.get('status')
        payment_status = request.data.get('payment_status')
        delivery_estimate = request.data.get('delivery_estimate')

        if status:
            valid_statuses = [choice[0] for choice in Order.STATUS_CHOICES]
            if status not in valid_statuses:
                return Response({"error": f"Invalid status: {status}"}, status=400)
            
            # Stock restoration logic
            if status in ['returned', 'cancelled'] and order.status not in ['returned', 'cancelled']:
                with transaction.atomic():
                    for item in order.items.all():
                        # Only restore stock for items that are not already cancelled or returned individually
                        if item.variant and not getattr(item, 'is_cancelled', False) and not getattr(item, 'is_returned', False):
                            item.variant.stock += item.quantity
                            item.variant.save()

            order.status = status
            if status == 'delivered' and order.payment_method == 'COD':
                order.payment_status = 'paid'

        if payment_status:
            valid_payment_statuses = ['pending', 'paid', 'failed']
            if payment_status not in valid_payment_statuses:
                return Response({"error": f"Invalid payment status: {payment_status}"}, status=400)
            order.payment_status = payment_status

        if delivery_estimate is not None:
            order.delivery_estimate = delivery_estimate

        order.save()
        serializer = OrderSerializer(order)
        return Response(serializer.data)