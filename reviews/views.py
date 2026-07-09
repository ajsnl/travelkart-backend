from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Review
from .serializers import ReviewSerializer, AdminReviewSerializer
from .services import ReviewService
from admin_panel.permissions import IsAdminUserRole

class IsOwnerOrReadOnly(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        # Safe methods (GET, HEAD, OPTIONS) are allowed for anyone.
        if request.method in permissions.SAFE_METHODS:
            return True
        # Only review owner or admin can edit/delete.
        return obj.user == request.user or (request.user.is_authenticated and request.user.role == 'admin')

class ReviewViewSet(viewsets.ModelViewSet):
    queryset = Review.objects.all()
    serializer_class = ReviewSerializer

    def get_permissions(self):
        if self.action in ['create']:
            permission_classes = [permissions.IsAuthenticated]
        elif self.action in ['update', 'partial_update', 'destroy']:
            permission_classes = [permissions.IsAuthenticated, IsOwnerOrReadOnly]
        else:
            permission_classes = [permissions.AllowAny]
        return [permission() for permission in permission_classes]

    def get_queryset(self):
        product_id = self.request.query_params.get('product')
        return ReviewService.get_active_reviews(product_id)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=False, methods=['get'], permission_classes=[permissions.IsAuthenticated])
    def check(self, request):
        """
        Check if the authenticated user can review a product.
        Query param: ?product=<product_id>
        """
        product_id = request.query_params.get('product')
        if not product_id:
            return Response({"error": "Product ID required"}, status=status.HTTP_400_BAD_REQUEST)

        result = ReviewService.check_eligibility(request.user, product_id)
        
        # Serialize existing review if any
        serialized_review = None
        if result["existing_review"]:
            serialized_review = ReviewSerializer(
                result["existing_review"], 
                context={'request': request}
            ).data

        return Response({
            "has_purchased": result["has_purchased"],
            "already_reviewed": result["already_reviewed"],
            "can_review": result["can_review"],
            "existing_review": serialized_review
        }, status=status.HTTP_200_OK)


class AdminReviewViewSet(viewsets.ModelViewSet):
    queryset = Review.objects.all()
    serializer_class = AdminReviewSerializer
    permission_classes = [IsAdminUserRole]

    def get_queryset(self):
        product_id = self.request.query_params.get('product')
        return ReviewService.get_all_reviews(product_id)
