from rest_framework.exceptions import NotFound
from .models import Review
from products.models import Product
from orders.models import OrderItem

class ReviewService:
    @staticmethod
    def get_active_reviews(product_id=None):
        """Retrieves active reviews, optionally filtered by product."""
        queryset = Review.objects.filter(is_active=True)
        if product_id:
            queryset = queryset.filter(product_id=product_id)
        return queryset.order_by('-created_at')

    @staticmethod
    def get_all_reviews(product_id=None):
        """Retrieves all reviews (active and inactive) for admin moderation, optionally filtered by product."""
        queryset = Review.objects.all()
        if product_id:
            queryset = queryset.filter(product_id=product_id)
        return queryset.order_by('-created_at')

    @staticmethod
    def check_eligibility(user, product_id):
        """Checks if a user is eligible to write a review for a specific product."""
        try:
            product = Product.objects.get(id=product_id)
        except Product.DoesNotExist:
            raise NotFound({"error": "Product not found"})

        already_reviewed = Review.objects.filter(user=user, product=product).exists()
        
        has_purchased = OrderItem.objects.filter(
            order__user=user,
            order__status='delivered',
            variant__product=product,
            is_cancelled=False,
            is_returned=False
        ).exists()

        can_review = has_purchased and not already_reviewed

        existing_review = None
        if already_reviewed:
            existing_review = Review.objects.filter(user=user, product=product).first()

        return {
            "has_purchased": has_purchased,
            "already_reviewed": already_reviewed,
            "can_review": can_review,
            "existing_review": existing_review
        }
