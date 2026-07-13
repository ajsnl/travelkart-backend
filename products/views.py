from rest_framework.decorators import action
from django.shortcuts import render
from rest_framework import viewsets, status
from rest_framework.filters import SearchFilter
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser

from admin_panel.permissions import IsAdminUserRole
from .models import Category, Product
from .serializers import (
    CategorySerializer,
    ProductListSerializer,
    ProductDetailSerializer,
    ProductWriteSerializer
)
from .services import CategoryService, ProductService, MediaService


class CategoryPagination(PageNumberPagination):
    page_size = 5
    page_size_query_param = 'page_size'
    max_page_size = 100


class AdminCategoryViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdminUserRole]
    queryset = Category.objects.filter(is_deleted=False).order_by('-created_at')
    serializer_class = CategorySerializer

    filter_backends = [SearchFilter]
    search_fields = ['name']

    pagination_class = CategoryPagination

    def get_queryset(self):
        queryset = Category.objects.filter(is_deleted=False).order_by('-created_at')
        cat_type = self.request.query_params.get('type')
        if cat_type == 'category':
            queryset = queryset.filter(parent__isnull=True)
        elif cat_type == 'subcategory':
            queryset = queryset.filter(parent__isnull=False)
        return queryset

    

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        CategoryService.soft_delete_category(instance)
        return Response({"message": "Category soft deleted"}, status=status.HTTP_200_OK)


class UserCategoryViewSet(viewsets.ReadOnlyModelViewSet):
    # Only show active and non-deleted categories to users
    queryset = Category.objects.filter(is_deleted=False, is_active=True).order_by('-created_at')
    serializer_class = CategorySerializer

    filter_backends = [SearchFilter]
    search_fields = ['name']

    pagination_class = CategoryPagination


class ProductPagination(PageNumberPagination):
    page_size = 9
    page_size_query_param = 'page_size'
    max_page_size = 100


class AdminProductViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdminUserRole]
    queryset = Product.objects.all().select_related('category__parent').prefetch_related('variants__images', 'images').order_by('-created_at')
    serializer_class = ProductDetailSerializer
    pagination_class = ProductPagination
    filter_backends = [SearchFilter]
    search_fields = ['name', 'brand', 'variants__sku']

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return ProductWriteSerializer
        return ProductDetailSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        return ProductService.filter_admin_products(queryset, self.request.query_params)

    @action(detail=False, methods=['get'])
    def brands(self, request):
        brands = ProductService.get_admin_brands()
        return Response(list(brands), status=status.HTTP_200_OK)


class UserProductViewSet(viewsets.ReadOnlyModelViewSet):
    # Default to all products (filtered dynamically in get_queryset for list vs retrieve)
    queryset = Product.objects.all().select_related('category__parent').prefetch_related('variants__images', 'images').order_by('-created_at')
    serializer_class = ProductDetailSerializer
    pagination_class = ProductPagination
    filter_backends = [SearchFilter]
    search_fields = ['name', 'brand', 'variants__sku']

    def get_queryset(self):
        queryset = super().get_queryset()
        return ProductService.filter_user_products(queryset, self.action, self.request.query_params)

    @action(detail=False, methods=['get'])
    def brands(self, request):
        brands = ProductService.get_user_brands()
        return Response(list(brands), status=status.HTTP_200_OK)


class UploadProductMediaView(APIView):
    permission_classes = [IsAdminUserRole]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        file_obj = request.data.get('file')
        try:
            result = MediaService.upload_product_media(file_obj)
            return Response(result, status=status.HTTP_200_OK)
        except Exception as e:
            # Check if it's already a ValidationError which Django/DRF knows how to render
            if hasattr(e, 'detail'):
                raise e
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
