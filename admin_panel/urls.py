from django.urls import path
from .views import AdminUserListView, ToggleUserBlockView, AdminOrderListView, AdminOrderDetailView

urlpatterns = [
    path('users/', AdminUserListView.as_view()),
    path('users/<int:user_id>/block/', ToggleUserBlockView.as_view()),
    path('orders/', AdminOrderListView.as_view(), name='admin-order-list'),
    path('orders/<str:tracking_id>/', AdminOrderDetailView.as_view(), name='admin-order-detail'),
]