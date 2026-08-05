from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django.db.models import Sum, Q
from django.db import transaction
from .serializers import AdminUserSerializer
from .permissions import IsAdminUserRole
from .services import AdminUserService, AdminStatsService
from orders.models import Order, AdminNotification
from orders.serializers import OrderSerializer
from orders.services import OrderService


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
            
            if status != order.status:
                ALLOWED_TRANSITIONS = {
                    'processing': ['shipped', 'cancelled'],
                    'shipped': ['out_for_delivery', 'cancelled'],
                    'out_for_delivery': ['delivered', 'cancelled'],
                    'delivered': ['return_requested', 'returned'],
                    'return_requested': ['returned', 'delivered'],
                    'cancelled': [],
                    'returned': []
                }
                allowed = ALLOWED_TRANSITIONS.get(order.status, [])
                if status not in allowed:
                    return Response({
                        "error": f"Cannot transition order from '{order.status}' to '{status}'. Allowed transitions: {', '.join(allowed) if allowed else 'None'}"
                    }, status=400)
            
            # Stock restoration logic
            if status in ['returned', 'cancelled'] and order.status not in ['returned', 'cancelled']:
                with transaction.atomic():
                    for item in order.items.all():
                        # Only restore stock for items that are not already cancelled or returned individually
                        if item.variant and not getattr(item, 'is_cancelled', False) and not getattr(item, 'is_returned', False):
                            item.variant.stock += item.quantity
                            item.variant.save()
                            if status == 'cancelled':
                                item.is_cancelled = True
                                item.cancel_reason = "Admin cancelled"
                            else:
                                item.is_returned = True
                                item.return_reason = "Admin returned"
                            item.save()

            order.status = status
            if status == 'delivered' and order.payment_method == 'COD':
                order.payment_status = 'paid'
            if status in ['cancelled', 'returned'] and order.payment_status == 'paid':
                order.payment_status = 'refunded'

        if payment_status:
            valid_payment_statuses = ['pending', 'paid', 'failed', 'refunded']
            if payment_status not in valid_payment_statuses:
                return Response({"error": f"Invalid payment status: {payment_status}"}, status=400)
            order.payment_status = payment_status

        if delivery_estimate is not None:
            order.delivery_estimate = delivery_estimate

        order.save()
        serializer = OrderSerializer(order)
        return Response(serializer.data)


class AdminNotificationListView(APIView):
    permission_classes = [IsAdminUserRole]
    
    def get(self, request):
        notifications = AdminNotification.objects.filter(is_read=False).order_by('-created_at')
        data = [{
            "id": n.id,
            "message": n.message,
            "tracking_id": n.tracking_id,
            "created_at": n.created_at.isoformat()
        } for n in notifications]
        return Response(data)


class AdminNotificationReadAllView(APIView):
    permission_classes = [IsAdminUserRole]
    
    def post(self, request):
        AdminNotification.objects.filter(is_read=False).update(is_read=True)
        return Response({"success": True})


class AdminOrderItemApproveReturnView(APIView):
    permission_classes = [IsAdminUserRole]
    
    def post(self, request, item_id):
        order = OrderService.approve_item_return(item_id, request.user)
        serializer = OrderSerializer(order)
        return Response(serializer.data)


class AdminOrderItemRejectReturnView(APIView):
    permission_classes = [IsAdminUserRole]
    
    def post(self, request, item_id):
        order = OrderService.reject_item_return(item_id, request.user)
        serializer = OrderSerializer(order)
        return Response(serializer.data)


class AdminDashboardStatsView(APIView):
    permission_classes = [IsAdminUserRole]

    def get(self, request):
        chart_filter = request.GET.get('chart_filter', 'daily')
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')

        response_data = AdminStatsService.get_dashboard_stats(
            chart_filter=chart_filter,
            start_date_str=start_date,
            end_date_str=end_date
        )
        return Response(response_data)


class AdminSalesReportView(APIView):
    permission_classes = [IsAdminUserRole]

    def get(self, request):
        report_type = request.GET.get('report_type', 'daily')
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')

        orders, summary = AdminStatsService.get_sales_report(
            report_type=report_type,
            start_date_str=start_date,
            end_date_str=end_date
        )

        export_all = request.GET.get('export', 'false').lower() == 'true'

        if not export_all:
            from rest_framework.pagination import PageNumberPagination
            paginator = PageNumberPagination()
            paginator.page_size = 10
            paginated_orders = paginator.paginate_queryset(orders, request)
        else:
            paginated_orders = orders

        orders_data = []
        for order in paginated_orders:
            orders_data.append({
                "id": order.id,
                "tracking_id": order.tracking_id,
                "customer_email": order.user.email,
                "customer_name": order.full_name,
                "created_at": order.created_at.isoformat(),
                "coupon_code": order.coupon_code or "N/A",
                "discount": float(order.discount),
                "total_price": float(order.total_price), # Net Amount
                "gross_price": float(order.total_price + order.discount), # Gross Amount
                "payment_status": order.payment_status,
                "status": order.status
            })

        if not export_all:
            response = paginator.get_paginated_response(orders_data)
            response.data['summary'] = summary
            return response
        else:
            return Response({
                "summary": summary,
                "orders": orders_data
            })