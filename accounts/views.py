from django.shortcuts import render

# Create your views here.
from rest_framework import generics, mixins
from .models import User
from .serializers import RegisterSerializer
from rest_framework.response import Response
from .serializers import LoginSerializer
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

class RegisterView(mixins.CreateModelMixin, generics.GenericAPIView):
    queryset = User.objects.all()
    serializer_class = RegisterSerializer

    def post(self, request, *args, **kwargs):
        return self.create(request, *args, **kwargs)
    







class LoginView(mixins.CreateModelMixin, generics.GenericAPIView):
    serializer_class = LoginSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data['user']

        refresh = RefreshToken.for_user(user)

        return Response({
            "user": {
                "email": user.email,
                "username": user.username,
                "phone": user.phone
            },
            "refresh": str(refresh),
            "access": str(refresh.access_token),
        }, status=status.HTTP_200_OK)