from django.urls import path,include
from rest_framework.routers import DefaultRouter
from .views import (
    AdminUserListView, ToggleUserBlockView, AdminOrderListView, 
    AdminOrderDetailView, AdminNotificationListView, AdminNotificationReadAllView,
    AdminOrderItemApproveReturnView, AdminOrderItemRejectReturnView
)
from promotions.views import AdminCouponViewSet

router=DefaultRouter()
router.register(r'coupons',AdminCouponViewSet,basename='admin-coupon')

urlpatterns = [
    path('users/', AdminUserListView.as_view()),
    path('users/<int:user_id>/block/', ToggleUserBlockView.as_view()),
    path('orders/', AdminOrderListView.as_view(), name='admin-order-list'),
    path('orders/<str:tracking_id>/', AdminOrderDetailView.as_view(), name='admin-order-detail'),
    path('notifications/', AdminNotificationListView.as_view(), name='admin-notifications'),
    path('notifications/read_all/', AdminNotificationReadAllView.as_view(), name='admin-notifications-read-all'),
    path('order-items/<int:item_id>/approve-return/', AdminOrderItemApproveReturnView.as_view()),
    path('order-items/<int:item_id>/reject-return/', AdminOrderItemRejectReturnView.as_view()),
    path('',include(router.urls)),
]