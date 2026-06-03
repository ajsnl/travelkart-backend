from django.shortcuts import render
from rest_framework import viewsets
from .models import Category
from .serializers import CategorySerializer
from rest_framework.filters import SearchFilter
from rest_framework.pagination import PageNumberPagination
from django.conf import settings 
from rest_framework.response import Response
from rest_framework import status
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
