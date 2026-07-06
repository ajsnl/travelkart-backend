from django.urls import path
from .views import UserCouponAvailableListView, UserCouponValidateView, UserActiveBannerListView

urlpatterns = [
    path('coupons/available/', UserCouponAvailableListView.as_view(), name='user-coupon-available'),
    path('coupons/validate/', UserCouponValidateView.as_view(), name='user-coupon-validate'),
    path('banners/active/', UserActiveBannerListView.as_view(), name='active-banners'),
]
