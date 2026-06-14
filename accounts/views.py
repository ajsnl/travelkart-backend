from django.shortcuts import render
from rest_framework import generics, mixins, viewsets, status
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser, FormParser
from django.http import JsonResponse
from django.views.decorators.csrf import ensure_csrf_cookie
from django.contrib.auth import get_user_model

from allauth.socialaccount.providers.google.views import GoogleOAuth2Adapter
from dj_rest_auth.registration.views import SocialLoginView

from .models import User, OTP, Address
from .serializers import (
    RegisterSerializer, LoginSerializer, ProfileSerializer,
    SendEmailOTPSerializer, VerifyEmailOTPSerializer,
    VerifyForgotPasswordOTPSerializer, ResetPasswordSerializer,
    ChangePasswordSerializer, AddressSerializer, ProfilePictureUploadSerializer
)
from .authentication import CookieJWTAuthentication, CookieJWTAuthenticationWithoutCSRF
from .services import AuthService, OtpService, PasswordService, AddressService, ProfileService

User = get_user_model()


class RegisterView(mixins.CreateModelMixin, generics.GenericAPIView):
    authentication_classes = []
    permission_classes = []
    queryset = User.objects.all()
    serializer_class = RegisterSerializer

    def post(self, request, *args, **kwargs):
        return self.create(request, *args, **kwargs)


@ensure_csrf_cookie
def get_csrf_token(request):
    return JsonResponse({"message": "CSRF cookie set"})


class LoginView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data["user"]
        tokens = AuthService.create_auth_tokens(user)

        response = Response({
            "message": "Login successful"
        }, status=status.HTTP_200_OK)

        AuthService.set_auth_cookies(
            response,
            access_token=tokens["access_token"],
            refresh_token=tokens["refresh_token"]
        )
        return response


class RefreshView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        refresh_token = request.COOKIES.get("refresh_token")
        if not refresh_token:
            return Response({"error": "No refresh token"}, status=status.HTTP_401_UNAUTHORIZED)

        try:
            new_access, new_refresh = AuthService.refresh_tokens(refresh_token)
            response = Response({"message": "Token refreshed"})
            AuthService.set_auth_cookies(response, new_access, new_refresh)
            return response
        except Exception:
            return Response({"error": "Invalid refresh token"}, status=status.HTTP_401_UNAUTHORIZED)


class ProfileView(mixins.RetrieveModelMixin,
                  mixins.UpdateModelMixin,
                  generics.GenericAPIView):
    serializer_class = ProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user

    def get(self, request, *args, **kwargs):
        return self.retrieve(request, *args, **kwargs)

    def put(self, request, *args, **kwargs):
        return self.update(request, *args, **kwargs)

    def patch(self, request, *args, **kwargs):
        return self.partial_update(request, *args, **kwargs)


class UserMeView(APIView):
    authentication_classes = [CookieJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({
            "email": request.user.email,
            "username": request.user.username,
            "phone": request.user.phone,
            "is_verified": request.user.is_verified,
            "is_gold_member": request.user.is_gold_member,
            "DateOfBirth": request.user.dob,
            "profile_picture": request.user.profile_picture.url if request.user.profile_picture else None,
            "updated_at": request.user.updated_at,
            "role": request.user.role
        })


class LogoutView(APIView):
    authentication_classes = [CookieJWTAuthenticationWithoutCSRF]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh_token = request.COOKIES.get("refresh_token")
        try:
            AuthService.blacklist_token(refresh_token)
        except Exception:
            pass  # token expired/invalid

        response = Response(
            {"message": "Logged out successfully"},
            status=status.HTTP_200_OK
        )
        AuthService.delete_auth_cookies(response)
        return response


class GoogleLogin(SocialLoginView):
    adapter_class = GoogleOAuth2Adapter
    permission_classes = [AllowAny]

    def get_response(self):
        if not self.user.is_verified:
            self.user.is_verified = True
            self.user.save()

        tokens = AuthService.create_auth_tokens(self.user)

        response = Response({
            "message": "Login successful",
            "user": {
                "username": self.user.username,
                "email": self.user.email
            }
        }, status=status.HTTP_200_OK)

        AuthService.set_auth_cookies(
            response,
            access_token=tokens["access_token"],
            refresh_token=tokens["refresh_token"]
        )
        return response


class SendEmailOTPView(mixins.CreateModelMixin, generics.GenericAPIView):
    serializer_class = SendEmailOTPSerializer
    permission_classes = [IsAuthenticated]

    def post(self, request):
        email = request.data.get('email')
        result = OtpService.send_email_otp(request.user, email)
        return Response(result, status=status.HTTP_200_OK)


class VerifyEmailOTPView(mixins.CreateModelMixin, generics.GenericAPIView):
    serializer_class = VerifyEmailOTPSerializer
    permission_classes = [IsAuthenticated]

    def post(self, request):
        otp_code = request.data.get('otp')
        result = OtpService.verify_email_otp(request.user, otp_code)
        return Response(result, status=status.HTTP_200_OK)


class ForgotPasswordView(generics.GenericAPIView):
    authentication_classes = []
    permission_classes = []
    serializer_class = SendEmailOTPSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']

        result = PasswordService.send_forgot_password_otp(email)
        return Response(result, status=status.HTTP_200_OK)


class ForgotPasswordVerifyOTPView(generics.GenericAPIView):
    authentication_classes = []
    permission_classes = []
    serializer_class = VerifyForgotPasswordOTPSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']
        otp_code = serializer.validated_data['otp']

        result = PasswordService.verify_forgot_password_otp(email, otp_code)
        return Response(result, status=status.HTTP_200_OK)


class ResendOTPView(mixins.CreateModelMixin, generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        result = OtpService.resend_email_otp(request.user)
        return Response(result, status=status.HTTP_200_OK)


class ResetPasswordView(generics.GenericAPIView):
    authentication_classes = []
    permission_classes = []
    serializer_class = ResetPasswordSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']
        new_password = serializer.validated_data['new_password']

        result = PasswordService.reset_password(email, new_password)
        return Response(result, status=status.HTTP_200_OK)


class ChangePasswordView(generics.GenericAPIView):
    serializer_class = ChangePasswordSerializer
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        old_password = serializer.validated_data['old_password']
        new_password = serializer.validated_data['new_password']

        result = PasswordService.change_password(request.user, old_password, new_password)
        return Response(result, status=status.HTTP_200_OK)


class AddressViewSet(viewsets.ModelViewSet):
    serializer_class = AddressSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Address.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        AddressService.create_address(self.request.user, serializer)

    def perform_update(self, serializer):
        AddressService.update_address(self.request.user, self.get_object(), serializer)

    def destroy(self, request, *args, **kwargs):
        address = self.get_object()
        AddressService.delete_address(address)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['patch'])
    def set_default(self, request, pk=None):
        address = self.get_object()
        AddressService.set_default_address(request.user, address)
        return Response({
            "message": "Default address set successfully"
        }, status=status.HTTP_200_OK)


class UploadProfilePicture(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def patch(self, request):
        user = request.user
        serializer = ProfilePictureUploadSerializer(user, data=request.data, partial=True)
        if serializer.is_valid():
            ProfileService.save_profile_picture(user, serializer)
            return Response({
                "message": "Profile picture updated",
                "image_url": user.profile_picture.url
            }, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
