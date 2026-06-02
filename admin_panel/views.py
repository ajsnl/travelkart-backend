from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django.contrib.auth import get_user_model
from .serializers import AdminUserSerializer
from .permissions import IsAdminUserRole
from django.db.models import Q

User = get_user_model()


class UserPagination(PageNumberPagination):
    page_size = 10


class AdminUserListView(APIView):
    permission_classes = [IsAdminUserRole]

    def get(self, request):
        search = request.GET.get('search')
        is_active = request.GET.get('is_active')
        is_gold = request.GET.get('is_gold')

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

        users = users.order_by('-date_joined')

        paginator = UserPagination()
        paginated_users = paginator.paginate_queryset(users, request)

        serializer = AdminUserSerializer(paginated_users, many=True)
        response = paginator.get_paginated_response(serializer.data)

        
        non_admins = User.objects.exclude(role='admin')
        total_members = non_admins.count()
        total_gold_members = non_admins.filter(is_gold_member=True).count()
        total_active_members = non_admins.filter(is_active=True).count()
        unverified_users = non_admins.filter(is_verified=False).count()

        response.data['stats'] = {
            "total_members": total_members,
            "total_gold_members": total_gold_members,
            "total_active_members": total_active_members,
            "unverified_users": unverified_users,
        }

        return response
    
class ToggleUserBlockView(APIView):
    permission_classes = [IsAdminUserRole]

    def patch(self, request, user_id):
        confirm = request.data.get("confirm")

        if confirm is not True:
            return Response(
                {"error": "Confirmation required to perform this action"},
                status=400
            )

        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=404)

        # Prevent self-block
        if request.user.id == user.id:
            return Response(
                {"error": "You cannot block yourself"},
                status=400
            )

        user.is_active = not user.is_active
        user.save()

        return Response({
            "message": "User blocked" if not user.is_active else "User unblocked",
            "is_active": user.is_active
        })