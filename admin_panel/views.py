from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from .serializers import AdminUserSerializer
from .permissions import IsAdminUserRole
from .services import AdminUserService


class UserPagination(PageNumberPagination):
    page_size = 10


class AdminUserListView(APIView):
    permission_classes = [IsAdminUserRole]

    def get(self, request):
        search = request.GET.get('search')
        is_active = request.GET.get('is_active')
        is_gold = request.GET.get('is_gold')

        users = AdminUserService.get_users_queryset(search, is_active, is_gold)

        paginator = UserPagination()
        paginated_users = paginator.paginate_queryset(users, request)

        serializer = AdminUserSerializer(paginated_users, many=True)
        response = paginator.get_paginated_response(serializer.data)

        stats = AdminUserService.get_user_stats()
        response.data['stats'] = stats

        return response
    


class ToggleUserBlockView(APIView):
    permission_classes = [IsAdminUserRole]

    def patch(self, request, user_id):
        confirm = request.data.get("confirm")
        
        user = AdminUserService.toggle_user_block(request.user, user_id, confirm)

        return Response({
            "message": "User blocked" if not user.is_active else "User unblocked",
            "is_active": user.is_active
        })