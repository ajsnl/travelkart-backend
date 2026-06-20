from django.urls import path
from .views import OrderCreateListView, OrderDetailView, OrderSimulateStatusView, OrderItemCancelView, OrderItemReturnView
urlpatterns = [
    path('', OrderCreateListView.as_view(), name='order-create-list'),
    path('items/<int:item_id>/cancel/', OrderItemCancelView.as_view(), name='order-item-cancel'),
    path('items/<int:item_id>/return/', OrderItemReturnView.as_view(), name='order-item-return'),
    path('<str:tracking_id>/', OrderDetailView.as_view(), name='order-detail'),
    path('<str:tracking_id>/simulate/', OrderSimulateStatusView.as_view(), name='order-simulate'),
]