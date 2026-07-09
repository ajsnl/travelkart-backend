from rest_framework import serializers
from .models import Review
from products.models import Product
from orders.models import OrderItem

class ReviewSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.username', read_only=True)
    user_email = serializers.CharField(source='user.email', read_only=True)
    user_profile_picture = serializers.SerializerMethodField()

    class Meta:
        model = Review
        fields = [
            'id', 'user', 'user_name', 'user_email', 'user_profile_picture',
            'product', 'rating', 'comment', 'created_at', 'updated_at', 'is_active'
        ]
        read_only_fields = ['user', 'is_active']

    def get_user_profile_picture(self, obj):
        if obj.user.profile_picture:
            return obj.user.profile_picture.url
        return None

    def validate_rating(self, value):
        if value < 1 or value > 5:
            raise serializers.ValidationError("Rating must be an integer between 1 and 5.")
        return value

    def validate(self, attrs):
        request = self.context.get('request')
        if not request or not request.user or not request.user.is_authenticated:
            raise serializers.ValidationError("Authentication required to submit a review.")

        user = request.user
        product = attrs.get('product')

        # If it's a creation (no instance yet)
        if not self.instance:
            # 1. Prevent duplicate reviews
            if Review.objects.filter(user=user, product=product).exists():
                raise serializers.ValidationError({"product": "You have already reviewed this product."})

            # 2. Only purchased users (verified buyers) should review
            has_purchased = OrderItem.objects.filter(
                order__user=user,
                order__status='delivered',
                variant__product=product,
                is_cancelled=False,
                is_returned=False
            ).exists()

            if not has_purchased:
                raise serializers.ValidationError({
                    "product": "Only verified buyers who have received their order can review this product."
                })

        return attrs

class AdminReviewSerializer(ReviewSerializer):
    class Meta(ReviewSerializer.Meta):
        read_only_fields = ['user']
