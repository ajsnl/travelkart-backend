from django.urls import path
from .views import AdminUserListView, ToggleUserBlockView

urlpatterns = [
    path('users/', AdminUserListView.as_view()),
    path('users/<int:user_id>/block/', ToggleUserBlockView.as_view()),
]