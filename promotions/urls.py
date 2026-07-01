from django.urls import path
from .views import UserCouponAvailableListView, UserCouponValidateView

urlpatterns = [
    path('coupons/available/', UserCouponAvailableListView.as_view(), name='user-coupon-available'),
    path('coupons/validate/', UserCouponValidateView.as_view(), name='user-coupon-validate'),
]
