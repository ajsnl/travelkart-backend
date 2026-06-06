from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import AdminCategoryViewSet, AdminProductViewSet, UploadProductMediaView

router = DefaultRouter()
router.register(r'categories', AdminCategoryViewSet, basename='admin-category')
router.register(r'products', AdminProductViewSet, basename='admin-product')

urlpatterns = [
    path('products/upload-media/', UploadProductMediaView.as_view(), name='admin_upload_product_media'),
    path('', include(router.urls)),
]
