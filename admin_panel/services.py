from django.db.models import Q
from django.contrib.auth import get_user_model
from rest_framework.exceptions import ValidationError, NotFound

User = get_user_model()

class AdminUserService:
    @staticmethod
    def get_users_queryset(search=None, is_active=None, is_gold=None):
        """Retrieves and filters all non-admin users."""
        users = User.objects.exclude(role='admin')

        if search:
            users = users.filter(
                Q(email__icontains=search) |
                Q(username__icontains=search)
            )

        if is_active is not None and is_active != "":
            users = users.filter(is_active=str(is_active).lower() == "true")

        if is_gold is not None and is_gold != "":
            users = users.filter(is_gold_member=str(is_gold).lower() == "true")

        return users.order_by('-date_joined')

    @staticmethod
    def get_user_stats():
        """Calculates user stats for admin panel dashboard."""
        non_admins = User.objects.exclude(role='admin')
        
        return {
            "total_members": non_admins.count(),
            "total_gold_members": non_admins.filter(is_gold_member=True).count(),
            "total_active_members": non_admins.filter(is_active=True).count(),
            "unverified_users": non_admins.filter(is_verified=False).count(),
        }

    @staticmethod
    def toggle_user_block(admin_user, user_id, confirm):
        """Toggles active state of a user with validations."""
        if confirm is not True:
            raise ValidationError({"error": "Confirmation required to perform this action"})

        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            raise NotFound({"error": "User not found"})

        # Prevent self-block
        if admin_user.id == user.id:
            raise ValidationError({"error": "You cannot block yourself"})

        user.is_active = not user.is_active
        user.save()
        return user
