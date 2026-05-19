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
        search = request.GET.get('search', '')
        is_active = request.GET.get('is_active')   # true / false
        is_gold = request.GET.get('is_gold')       # true / false

        users = User.objects.all()

        # 🔍 Search (email)
        if search:
            users = users.filter(
                Q(email__icontains=search) |
                Q(username__icontains=search)
             )

        # 🔐 Filter by active / blocked
        if is_active is not None:
            if is_active.lower() == "true":
                users = users.filter(is_active=True)
            elif is_active.lower() == "false":
                users = users.filter(is_active=False)

        # 💎 Filter by gold membership
        if is_gold is not None:
            if is_gold.lower() == "true":
                users = users.filter(is_gold_member=True)
            elif is_gold.lower() == "false":
                users = users.filter(is_gold_member=False)

        # ⬇️ Sort (latest first)
        users = users.order_by('-date_joined')

        # 📄 Pagination
        paginator = UserPagination()
        paginated_users = paginator.paginate_queryset(users, request)

        serializer = AdminUserSerializer(paginated_users, many=True)
        return paginator.get_paginated_response(serializer.data)
    
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

        # 🚫 Prevent self-block
        if request.user.id == user.id:
            return Response(
                {"error": "You cannot block yourself"},
                status=400
            )

        # 🔁 Toggle block/unblock
        user.is_active = not user.is_active
        user.save()

        return Response({
            "message": "User blocked" if not user.is_active else "User unblocked",
            "is_active": user.is_active
        })