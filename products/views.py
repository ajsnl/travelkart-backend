from rest_framework.decorators import action
from django.shortcuts import render
from rest_framework import viewsets
from .models import Category, Product
from .serializers import CategorySerializer, ProductSerializer
from rest_framework.filters import SearchFilter
from rest_framework.pagination import PageNumberPagination
from django.conf import settings 
from rest_framework.response import Response
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser
from django.core.files.storage import default_storage

# Create your views here.

class CategoryPagination(PageNumberPagination):
    page_size = 5

class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.filter(is_deleted=False).order_by('-created_at')
    serializer_class=CategorySerializer

    filter_backends = [SearchFilter]
    search_fields = ['name']

    pagination_class = CategoryPagination

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.is_deleted = True
        instance.save()
        return Response({"message": "Category soft deleted"}, status=status.HTTP_200_OK)


class ProductPagination(PageNumberPagination):
    page_size = 10


class ProductViewSet(viewsets.ModelViewSet):
    # Optimize query with select_related and prefetch_related to prevent N+1 queries
    queryset = Product.objects.all().select_related('category').prefetch_related('variants__images', 'images').order_by('-created_at')
    serializer_class = ProductSerializer
    pagination_class = ProductPagination
    filter_backends = [SearchFilter]
    search_fields = ['name', 'brand', 'variants__sku']

    def get_queryset(self):
        queryset = super().get_queryset()
        category = self.request.query_params.get('category')
        brand = self.request.query_params.get('brand')
        is_active = self.request.query_params.get('is_active')
        is_featured = self.request.query_params.get('is_featured')

        if category:
            queryset = queryset.filter(category_id=category)
        if brand:
            queryset = queryset.filter(brand__iexact=brand)
        if is_active is not None:
            is_active_bool = is_active.lower() in ['true', '1']
            queryset = queryset.filter(is_active=is_active_bool)
        if is_featured is not None:
            is_featured_bool = is_featured.lower() in ['true', '1']
            queryset = queryset.filter(is_featured=is_featured_bool)

        user = self.request.user
        is_admin = user and user.is_authenticated and getattr(user, 'role', 'user') == 'admin'
        if not is_admin:
            queryset = queryset.filter(is_active=True)

        return queryset

    @action(detail=False, methods=['get'])
    def brands(self, request):
        brands = Product.objects.exclude(brand__isnull=True).exclude(brand="").values_list('brand', flat=True).distinct().order_by('brand')
        return Response(list(brands))


class UploadProductMediaView(APIView):
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        file_obj = request.data.get('file')
        if not file_obj:
            return Response({"error": "No file provided"}, status=status.HTTP_400_BAD_REQUEST)
        
        # Save file to default storage (Cloudinary)
        try:
            file_name = default_storage.save(f"travelkart/products/{file_obj.name}", file_obj)
            file_url = default_storage.url(file_name)
            return Response({
                "message": "Upload successful",
                "image_url": file_url
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
