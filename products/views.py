from rest_framework.decorators import action
from django.shortcuts import render
from rest_framework import viewsets
from .models import Category, Product
from .serializers import (
    CategorySerializer,
    ProductListSerializer,
    ProductDetailSerializer,
    ProductWriteSerializer
)
from rest_framework.filters import SearchFilter
from rest_framework.pagination import PageNumberPagination
from django.conf import settings 
from rest_framework.response import Response
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser
from django.core.files.storage import default_storage
from admin_panel.permissions import IsAdminUserRole

# Create your views here.

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

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.is_deleted = True
        instance.save()
        return Response({"message": "Category soft deleted"}, status=status.HTTP_200_OK)


class UserCategoryViewSet(viewsets.ReadOnlyModelViewSet):
    # Only show active and non-deleted categories to users
    queryset = Category.objects.filter(is_deleted=False, is_active=True).order_by('-created_at')
    serializer_class = CategorySerializer

    filter_backends = [SearchFilter]
    search_fields = ['name']

    pagination_class = CategoryPagination


class ProductPagination(PageNumberPagination):
    page_size = 10
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
        category = self.request.query_params.get('category')
        brand = self.request.query_params.get('brand')
        is_active = self.request.query_params.get('is_active')
        is_featured = self.request.query_params.get('is_featured')

        if category:
            from django.db.models import Q
            subcategories = Category.objects.filter(parent_id=category, is_deleted=False)
            subcategory_ids = list(subcategories.values_list('id', flat=True))
            if subcategory_ids:
                queryset = queryset.filter(Q(category_id=category) | Q(category_id__in=subcategory_ids))
            else:
                queryset = queryset.filter(category_id=category)
        if brand:
            queryset = queryset.filter(brand__iexact=brand)
        if is_active is not None:
            is_active_bool = is_active.lower() in ['true', '1']
            queryset = queryset.filter(is_active=is_active_bool)
        if is_featured is not None:
            is_featured_bool = is_featured.lower() in ['true', '1']
            queryset = queryset.filter(is_featured=is_featured_bool)

        return queryset

    @action(detail=False, methods=['get'])
    def brands(self, request):
        brands = Product.objects.exclude(brand__isnull=True).exclude(brand="").values_list('brand', flat=True).distinct().order_by('brand')
        return Response(list(brands))


class UserProductViewSet(viewsets.ReadOnlyModelViewSet):
    # Default to all products (filtered dynamically in get_queryset for list vs retrieve)
    queryset = Product.objects.all().select_related('category__parent').prefetch_related('variants__images', 'images').order_by('-created_at')
    serializer_class = ProductDetailSerializer
    pagination_class = ProductPagination
    filter_backends = [SearchFilter]
    search_fields = ['name', 'brand', 'variants__sku']

    def get_queryset(self):
        queryset = super().get_queryset()
        
        # 1. Apply visibility checks based on action
        if self.action == 'list':
            queryset = queryset.filter(is_active=True)
            # Only show products in active and non-deleted categories
            queryset = queryset.filter(category__is_active=True, category__is_deleted=False)
            # Exclude products whose parent category is inactive or deleted
            queryset = queryset.exclude(category__parent__is_active=False).exclude(category__parent__is_deleted=True)
        elif self.action == 'retrieve':
            # Allow viewing but ensure category itself is not deleted
            queryset = queryset.filter(category__is_deleted=False).exclude(category__parent__is_deleted=True)

        category = self.request.query_params.get('category')
        brand = self.request.query_params.get('brand')
        is_featured = self.request.query_params.get('is_featured')

        if category:
            from django.db.models import Q
            subcategories = Category.objects.filter(parent_id=category, is_active=True, is_deleted=False)
            subcategory_ids = list(subcategories.values_list('id', flat=True))
            if subcategory_ids:
                queryset = queryset.filter(Q(category_id=category) | Q(category_id__in=subcategory_ids))
            else:
                queryset = queryset.filter(category_id=category)
        if brand:
            queryset = queryset.filter(brand__iexact=brand)
        if is_featured is not None:
            is_featured_bool = is_featured.lower() in ['true', '1']
            queryset = queryset.filter(is_featured=is_featured_bool)

        # Price range filter
        min_price = self.request.query_params.get('min_price')
        max_price = self.request.query_params.get('max_price')
        if min_price or max_price:
            from django.db.models import Q
            price_query = Q(variants__is_active=True)
            if min_price:
                price_query &= Q(variants__price__gte=min_price)
            if max_price:
                price_query &= Q(variants__price__lte=max_price)
            queryset = queryset.filter(price_query).distinct()

        # Sorting
        ordering = self.request.query_params.get('ordering')
        if ordering:
            from django.db.models import Min, Q
            if ordering == 'price_asc':
                queryset = queryset.annotate(min_active_price=Min('variants__price', filter=Q(variants__is_active=True))).order_by('min_active_price')
            elif ordering == 'price_desc':
                queryset = queryset.annotate(min_active_price=Min('variants__price', filter=Q(variants__is_active=True))).order_by('-min_active_price')
            elif ordering == 'name_asc':
                queryset = queryset.order_by('name')
            elif ordering == 'name_desc':
                queryset = queryset.order_by('-name')

        return queryset

    @action(detail=False, methods=['get'])
    def brands(self, request):
        brands = Product.objects.filter(is_active=True).exclude(brand__isnull=True).exclude(brand="").values_list('brand', flat=True).distinct().order_by('brand')
        return Response(list(brands))


class UploadProductMediaView(APIView):
    permission_classes = [IsAdminUserRole]
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
