from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ReviewViewSet, AdminReviewViewSet

router = DefaultRouter()
router.register(r'user', ReviewViewSet, basename='review')
router.register(r'admin', AdminReviewViewSet, basename='admin-review')

urlpatterns = [
    path('', include(router.urls)),
]
