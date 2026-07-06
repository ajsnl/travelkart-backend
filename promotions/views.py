from rest_framework import viewsets, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import action
from django.utils import timezone
from django.db.models import Sum
from .models import Coupon, Banner
from .serializers import CouponSerializer, BannerSerializer
from .services import BannerService, CouponService
from admin_panel.permissions import IsAdminUserRole
from cart.services import CartService
from orders.models import Order

class AdminCouponViewSet(viewsets.ModelViewSet):
    queryset = Coupon.objects.all().order_by('-id')
    serializer_class = CouponSerializer
    permission_classes = [IsAdminUserRole]

    def list(self, request, *args, **kwargs):
        search = request.query_params.get('search')
        status_filter = request.query_params.get('status')
        type_filter = request.query_params.get('type')

        # Retrieve filtered queryset from service
        queryset = CouponService.get_filtered_coupons(
            search=search,
            status_filter=status_filter,
            type_filter=type_filter
        )
        queryset = self.filter_queryset(queryset)

        page = self.paginate_queryset(queryset)
        stats = CouponService.get_coupon_stats()

        if page is not None:
            serializer = self.get_serializer(page, many=True)
            response = self.get_paginated_response(serializer.data)
            response.data['stats'] = stats
            return response
            
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            "results": serializer.data,
            "stats": stats
        })


class UserCouponAvailableListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        # Retrieve available coupons from service
        available_coupons = CouponService.get_available_coupons(request.user)
        return Response(available_coupons)


class UserCouponValidateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        code = request.data.get('code', '')
        # validate_coupon raises ValidationError if invalid or expired
        result = CouponService.validate_coupon(request.user, code)
        return Response(result)


class AdminBannerViewSet(viewsets.ModelViewSet):
    queryset = Banner.objects.all().order_by('-id')
    serializer_class = BannerSerializer
    permission_classes = [IsAdminUserRole]

    def list(self, request, *args, **kwargs):
        search = request.query_params.get('search')
        status_filter = request.query_params.get('status')
        position_filter = request.query_params.get('position')

        # Retrieve filtered queryset from service
        queryset = BannerService.get_filtered_banners(
            search=search,
            status_filter=status_filter,
            position_filter=position_filter
        )
        queryset = self.filter_queryset(queryset)

        page = self.paginate_queryset(queryset)
        stats = BannerService.get_banner_stats()

        if page is not None:
            serializer = self.get_serializer(page, many=True)
            response = self.get_paginated_response(serializer.data)
            response.data['stats'] = stats
            return response
            
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            "results": serializer.data,
            "stats": stats
        })


class UserActiveBannerListView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        position = request.query_params.get('position')
        
        # Retrieve active banners from service
        queryset = BannerService.get_active_banners(position_filter=position)
            
        serializer = BannerSerializer(queryset, many=True, context={'request': request})
        return Response(serializer.data)
