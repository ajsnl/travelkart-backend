from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import UserCategoryViewSet, UserProductViewSet

router = DefaultRouter()
router.register(r'categories', UserCategoryViewSet, basename='user-category')
router.register(r'products', UserProductViewSet, basename='user-product')

urlpatterns = [
    path('', include(router.urls)),
]
