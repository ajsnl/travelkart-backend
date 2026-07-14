from django.db.models import Q
from django.contrib.auth import get_user_model
from rest_framework.exceptions import ValidationError, NotFound

User = get_user_model()

class AdminUserService:
    @staticmethod
    def get_users_queryset(search=None, is_active=None, is_gold=None):
        """Retrieves and filters all non-admin users."""
        users = User.objects.exclude(role='admin')

        if search:
            users = users.filter(
                Q(email__icontains=search) |
                Q(username__icontains=search)
            )

        if is_active is not None and is_active != "":
            users = users.filter(is_active=str(is_active).lower() == "true")

        if is_gold is not None and is_gold != "":
            users = users.filter(is_gold_member=str(is_gold).lower() == "true")

        return users.order_by('-date_joined')

    @staticmethod
    def get_user_stats():
        """Calculates user stats for admin panel dashboard."""
        non_admins = User.objects.exclude(role='admin')
        
        return {
            "total_members": non_admins.count(),
            "total_gold_members": non_admins.filter(is_gold_member=True).count(),
            "total_active_members": non_admins.filter(is_active=True).count(),
            "unverified_users": non_admins.filter(is_verified=False).count(),
        }

    @staticmethod
    def toggle_user_block(admin_user, user_id, confirm):
        """Toggles active state of a user with validations."""
        if confirm is not True:
            raise ValidationError({"error": "Confirmation required to perform this action"})

        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            raise NotFound({"error": "User not found"})

        # Prevent self-block
        if admin_user.id == user.id:
            raise ValidationError({"error": "You cannot block yourself"})

        user.is_active = not user.is_active
        user.save()
        return user


class AdminStatsService:
    @staticmethod
    def get_dashboard_stats(chart_filter, start_date_str=None, end_date_str=None):
        from datetime import timedelta
        from django.utils import timezone
        from django.db.models.functions import TruncDay, TruncWeek, TruncMonth, TruncYear
        from django.db.models import Count, Sum, F
        from orders.models import Order, OrderItem
        from datetime import datetime

        now = timezone.now()
        
        all_orders = Order.objects.all()
        valid_orders = all_orders.exclude(status__in=['cancelled', 'returned'])
        
        total_revenue = valid_orders.aggregate(sum=Sum('total_price'))['sum'] or 0.00
        
        # Monthly Revenue 
        start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        monthly_revenue = valid_orders.filter(created_at__gte=start_of_month).aggregate(sum=Sum('total_price'))['sum'] or 0.00
        
        # Weekly Revenue 
        start_of_week = now - timedelta(days=7)
        weekly_revenue = valid_orders.filter(created_at__gte=start_of_week).aggregate(sum=Sum('total_price'))['sum'] or 0.00
        
        # Average Order Value 
        valid_orders_count = valid_orders.count()
        aov = float(total_revenue) / valid_orders_count if valid_orders_count > 0 else 0.00

        #  Sales chart 
        chart_data = []

        if chart_filter == 'daily':
            # Last 30 days
            start_date = now - timedelta(days=30)
            sales_by_date = valid_orders.filter(created_at__gte=start_date)\
                .annotate(date=TruncDay('created_at'))\
                .values('date')\
                .annotate(sales=Sum('total_price'), count=Count('id'))\
                .order_by('date')
            for entry in sales_by_date:
                chart_data.append({
                    "label": entry['date'].strftime('%b %d'),
                    "sales": float(entry['sales'] or 0),
                    "orders": entry['count']
                })
        elif chart_filter == 'weekly':
            # Last 12 weeks
            start_date = now - timedelta(weeks=12)
            sales_by_week = valid_orders.filter(created_at__gte=start_date)\
                .annotate(week=TruncWeek('created_at'))\
                .values('week')\
                .annotate(sales=Sum('total_price'), count=Count('id'))\
                .order_by('week')
            for entry in sales_by_week:
                chart_data.append({
                    "label": "Wk " + entry['week'].strftime('%W'),
                    "sales": float(entry['sales'] or 0),
                    "orders": entry['count']
                })
        elif chart_filter == 'monthly':
            # Last 12 months
            start_date = now - timedelta(days=365)
            sales_by_month = valid_orders.filter(created_at__gte=start_date)\
                .annotate(month=TruncMonth('created_at'))\
                .values('month')\
                .annotate(sales=Sum('total_price'), count=Count('id'))\
                .order_by('month')
            for entry in sales_by_month:
                chart_data.append({
                    "label": entry['month'].strftime('%b %Y'),
                    "sales": float(entry['sales'] or 0),
                    "orders": entry['count']
                })
        elif chart_filter == 'yearly':
            # Last 5 years
            start_date = now - timedelta(days=365 * 5)
            sales_by_year = valid_orders.filter(created_at__gte=start_date)\
                .annotate(year=TruncYear('created_at'))\
                .values('year')\
                .annotate(sales=Sum('total_price'), count=Count('id'))\
                .order_by('year')
            for entry in sales_by_year:
                chart_data.append({
                    "label": entry['year'].strftime('%Y'),
                    "sales": float(entry['sales'] or 0),
                    "orders": entry['count']
                })
        else: # 'custom'
            if start_date_str and end_date_str:
                try:
                    start_date = timezone.make_aware(datetime.strptime(start_date_str, '%Y-%m-%d'))
                    end_date = timezone.make_aware(datetime.strptime(end_date_str, '%Y-%m-%d')).replace(hour=23, minute=59, second=59, microsecond=999999)
                except ValueError:
                    start_date = now - timedelta(days=30)
                    end_date = now
            else:
                start_date = now - timedelta(days=30)
                end_date = now

            diff_days = (end_date - start_date).days
            if diff_days <= 60:
                trunc_func = TruncDay('created_at')
                label_format = '%b %d'
            elif diff_days <= 365:
                trunc_func = TruncWeek('created_at')
                label_format = 'Wk %W'
            else:
                trunc_func = TruncMonth('created_at')
                label_format = '%b %Y'

            sales_by_range = valid_orders.filter(created_at__range=(start_date, end_date))\
                .annotate(point=trunc_func)\
                .values('point')\
                .annotate(sales=Sum('total_price'), count=Count('id'))\
                .order_by('point')

            for entry in sales_by_range:
                chart_data.append({
                    "label": entry['point'].strftime(label_format),
                    "sales": float(entry['sales'] or 0),
                    "orders": entry['count']
                })

        # 3.  Top Products & Top Categories
        valid_items = OrderItem.objects.filter(
            order__status__in=['processing', 'shipped', 'out_for_delivery', 'delivered', 'return_requested'],
            is_cancelled=False,
            is_returned=False
        )
        
        top_products_query = valid_items.values(
            'variant__product__id',
            'variant__product__name'
        ).annotate(
            units_sold=Sum('quantity'),
            revenue=Sum(F('price') * F('quantity'))
        ).order_by('-units_sold')[:5]

        top_products = []
        for item in top_products_query:
            top_products.append({
                "id": item['variant__product__id'],
                "name": item['variant__product__name'],
                "units_sold": item['units_sold'],
                "revenue": float(item['revenue'] or 0)
            })

        # Top Categories
        top_categories_query = valid_items.values(
            'variant__product__category__id',
            'variant__product__category__name'
        ).annotate(
            units_sold=Sum('quantity'),
            revenue=Sum(F('price') * F('quantity'))
        ).order_by('-units_sold')[:5]

        top_categories = []
        for item in top_categories_query:
            top_categories.append({
                "id": item['variant__product__category__id'],
                "name": item['variant__product__category__name'],
                "units_sold": item['units_sold'],
                "revenue": float(item['revenue'] or 0)
            })

        # Returns / Orders stats
        total_orders = all_orders.count()
        processing_count = all_orders.filter(status='processing').count()
        shipped_count = all_orders.filter(status='shipped').count()
        delivered_count = all_orders.filter(status='delivered').count()
        cancelled_count = all_orders.filter(status='cancelled').count()
        returned_count = all_orders.filter(status='returned').count()
        return_requested_count = all_orders.filter(status='return_requested').count()
        
        return_rate = (returned_count / total_orders * 100) if total_orders > 0 else 0.0

        order_stats = {
            "total_orders": total_orders,
            "processing": processing_count,
            "shipped": shipped_count,
            "delivered": delivered_count,
            "cancelled": cancelled_count,
            "returned": returned_count,
            "return_requested": return_requested_count,
            "return_rate": round(return_rate, 2)
        }

        return {
            "revenue": {
                "total_revenue": float(total_revenue),
                "monthly_revenue": float(monthly_revenue),
                "weekly_revenue": float(weekly_revenue),
                "aov": float(aov),
                "valid_orders_count": valid_orders_count
            },
            "chart_data": chart_data,
            "top_products": top_products,
            "top_categories": top_categories,
            "order_stats": order_stats
        }

    @staticmethod
    def get_sales_report(report_type, start_date_str=None, end_date_str=None):
        from datetime import datetime, timedelta
        from django.utils import timezone
        from django.db.models import Sum
        from orders.models import Order

        now = timezone.now()

        # Determine Date Range
        if report_type == 'daily':
            start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = now.replace(hour=23, minute=59, second=59, microsecond=999999)
        elif report_type == 'weekly':
            start_date = (now - timedelta(days=7)).replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = now.replace(hour=23, minute=59, second=59, microsecond=999999)
        elif report_type == 'monthly':
            start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            end_date = now.replace(hour=23, minute=59, second=59, microsecond=999999)
        elif report_type == 'yearly':
            start_date = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            end_date = now.replace(hour=23, minute=59, second=59, microsecond=999999)
        else: # 'custom'
            if start_date_str and end_date_str:
                try:
                    start_date = timezone.make_aware(datetime.strptime(start_date_str, '%Y-%m-%d'))
                    end_date = timezone.make_aware(datetime.strptime(end_date_str, '%Y-%m-%d')).replace(hour=23, minute=59, second=59, microsecond=999999)
                except ValueError:
                    start_date = now - timedelta(days=30)
                    end_date = now
            else:
                start_date = now - timedelta(days=30)
                end_date = now

        # Query valid orders (excluding cancelled & returned)
        orders = Order.objects.filter(
            created_at__range=(start_date, end_date)
        ).exclude(status__in=['cancelled', 'returned']).order_by('-created_at')

        # Calculations
        overall_sales_count = orders.count()
        total_discount = orders.aggregate(sum=Sum('discount'))['sum'] or 0.00
        net_revenue = orders.aggregate(sum=Sum('total_price'))['sum'] or 0.00
        gross_revenue = float(net_revenue) + float(total_discount)

        summary = {
            "sales_count": overall_sales_count,
            "gross_amount": round(gross_revenue, 2),
            "discount_amount": float(total_discount),
            "net_amount": float(net_revenue)
        }

        return orders, summary
