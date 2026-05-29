from django.shortcuts import render

# Create your views here.
from rest_framework import generics, mixins,viewsets
from .models import User,OTP,Address
from django.utils import timezone
from django.contrib.auth import get_user_model
from datetime import timedelta
from .serializers import RegisterSerializer,LoginSerializer,ProfileSerializer,SendEmailOTPSerializer,VerifyEmailOTPSerializer,VerifyForgotPasswordOTPSerializer,ResetPasswordSerializer
from .serializers import ChangePasswordSerializer,AddressSerializer
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .serializers import LoginSerializer
from rest_framework import status
from rest_framework.views import APIView
from .utils import create_otp,send_otp_email
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken, BlacklistedToken
from django.http import JsonResponse
from django.views.decorators.csrf import ensure_csrf_cookie
from .authentication import CookieJWTAuthentication, CookieJWTAuthenticationWithoutCSRF


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

        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)
        refresh_token = str(refresh)

        response = Response({
            "message": "Login successful"
        }, status=status.HTTP_200_OK)

        # ✅ SET ACCESS TOKEN COOKIE
        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=True,
            secure=False,      # True in production (HTTPS)
            samesite="Lax",
            path="/",
        )

        # ✅ SET REFRESH TOKEN COOKIE
        response.set_cookie(
            key="refresh_token",
            value=refresh_token,
            httponly=True,
            secure=False,
            samesite="Lax",
            path="/",
        )

        return response
    


class RefreshView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        refresh_token = request.COOKIES.get("refresh_token")

        if not refresh_token:
            return Response({"error": "No refresh token"}, status=401)

        try:
            refresh = RefreshToken(refresh_token)

            # 🔥 NEW TOKENS
            new_access = str(refresh.access_token)
            new_refresh = str(refresh)  # optional but recommended

            response = Response({"message": "Token refreshed"})

            # ✅ set access token
            response.set_cookie(
                key="access_token",
                value=new_access,
                httponly=True,
                secure=False,
                samesite="Lax",
                path="/",   # 🔥 IMPORTANT
            )

            # ✅ ALSO RESET REFRESH TOKEN
            response.set_cookie(
                key="refresh_token",
                value=new_refresh,
                httponly=True,
                secure=False,
                samesite="Lax",
                path="/",   # 🔥 IMPORTANT
            )

            return response

        except Exception:
            return Response({"error": "Invalid refresh token"}, status=401)

class ProfileView(mixins.RetrieveModelMixin,
                  mixins.UpdateModelMixin,
                  generics.GenericAPIView):

    serializer_class = ProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user  # 🔥 logged-in user

    # ✅ GET → fetch profile
    def get(self, request, *args, **kwargs):
        return self.retrieve(request, *args, **kwargs)

    # ✅ PUT → full update
    def put(self, request, *args, **kwargs):
        return self.update(request, *args, **kwargs)

    # ✅ PATCH → partial update
    def patch(self, request, *args, **kwargs):
        return self.partial_update(request, *args, **kwargs)    
    




class UserMeView(APIView):
    authentication_classes = [CookieJWTAuthentication]  # 🔥 ADD THIS
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({
            "email": request.user.email,
            "username": request.user.username,
            "phone": request.user.phone,
            "is_verified": request.user.is_verified,
            "is_gold_member": request.user.is_gold_member,
            "DateOfBirth":request.user.dob

        })


from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken

class LogoutView(APIView):
    authentication_classes = [CookieJWTAuthenticationWithoutCSRF]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh_token = request.COOKIES.get("refresh_token")

        # 🔥 Try to blacklist token (but don't break logout)
        if refresh_token:
            try:
                token = RefreshToken(refresh_token)
                token.blacklist()
            except Exception:
                pass  # ignore errors (token expired/invalid)

        response = Response(
            {"message": "Logged out successfully"},
            status=status.HTTP_200_OK
        )

        # 🔥 IMPORTANT: match cookie settings used during login
        response.delete_cookie(
            "access_token",
            path="/",
            samesite="Lax",
        )
        response.delete_cookie(
            "refresh_token",
            path="/",
            samesite="Lax",
        )

        return response
    
from allauth.socialaccount.providers.google.views import GoogleOAuth2Adapter
from dj_rest_auth.registration.views import SocialLoginView
from rest_framework.permissions import AllowAny

class GoogleLogin(SocialLoginView):
    adapter_class = GoogleOAuth2Adapter
    permission_classes = [AllowAny]

    def get_response(self):
        # Mark user as verified if they log in via Google
        if not self.user.is_verified:
            self.user.is_verified = True
            self.user.save()

        # Generate JWT tokens for the authenticated user
        refresh = RefreshToken.for_user(self.user)
        access_token = str(refresh.access_token)
        refresh_token = str(refresh)

        response = Response({
            "message": "Login successful",
            "user": {
                "username": self.user.username,
                "email": self.user.email
            }
        }, status=status.HTTP_200_OK)

        # Set HttpOnly cookies matching LoginView settings
        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=True,
            secure=False,      # True in production (HTTPS)
            samesite="Lax",
            path="/",
        )
        response.set_cookie(
            key="refresh_token",
            value=refresh_token,
            httponly=True,
            secure=False,
            samesite="Lax",
            path="/",
        )
        return response


class SendEmailOTPView(mixins.CreateModelMixin, generics.GenericAPIView):
    serializer_class = SendEmailOTPSerializer
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        email = request.data.get('email')

        # 🧠 HANDLE BOTH CASES

        # ✅ CASE 1: Email update
        if email:
            # 🚫 check duplicate
            if User.objects.filter(email=email).exists():
                return Response({"error": "Email already in use"}, status=400)

            user.temp_email = email
            user.is_verified = False

        # ✅ CASE 2: Signup verification (no email passed)
        else:
            if not user.email:
                return Response({"error": "No email found"}, status=400)

            user.temp_email = user.email  # 🔥 important

        user.save()

        # 🔐 create OTP
        otp_obj = create_otp(user, 'email_verify')
        send_otp_email(user.temp_email, otp_obj.otp_code)

        return Response({"message": "OTP sent to email"}, status=200)




class VerifyEmailOTPView(mixins.CreateModelMixin, generics.GenericAPIView):
    serializer_class = VerifyEmailOTPSerializer
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        otp_code = request.data.get('otp')

        if not otp_code:
            return Response({"error": "OTP is required"}, status=400)

        # 🔍 get latest valid OTP
        otp = OTP.objects.filter(
            user=user,
            otp_code=otp_code,
            purpose='email_verify',
            is_used=False
        ).order_by('-created_at').first()

        if not otp:
            return Response({"error": "Invalid OTP"}, status=400)

        # ⏱️ check expiry
        if otp.expires_at < timezone.now():
            return Response({"error": "OTP expired"}, status=400)

        # 🚨 CRITICAL FIX
        if not user.temp_email:
            return Response({"error": "No email to verify"}, status=400)

        # 🚫 prevent duplicate emails
        if User.objects.filter(email=user.temp_email).exclude(id=user.id).exists():
            return Response({"error": "Email already in use"}, status=400)

        # ✅ mark OTP used
        otp.is_used = True
        otp.save()

        # ✅ update email safely
        user.email = user.temp_email
        user.temp_email = None
        user.is_verified = True
        user.save()

        return Response({"message": "Email verified successfully"}, status=200)

from django.utils import timezone
from datetime import timedelta

class ForgotPasswordView(generics.GenericAPIView):
    authentication_classes = []
    permission_classes = []
    serializer_class = SendEmailOTPSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data['email']

        if not email:
            return Response({"error": "Email is required"}, status=400)

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=404)

        # 🔥 1. Cooldown check (60 sec)
        last_otp = OTP.objects.filter(
            user=user,
            purpose="password_reset"
        ).order_by('-created_at').first()

        if last_otp and (timezone.now() - last_otp.created_at).seconds < 60:
            return Response(
                {"error": "Please wait before requesting another OTP"},
                status=429
            )

        # 🔥 2. Invalidate old OTPs
        OTP.objects.filter(
            user=user,
            purpose="password_reset",
            is_used=False
        ).update(is_used=True)

        # 🔥 3. Create new OTP
        otp_obj = create_otp(user, "password_reset")

        send_otp_email(user.email, otp_obj.otp_code)

        return Response({"message": "OTP sent successfully"}, status=200)
    


User = get_user_model()

class ForgotPasswordVerifyOTPView(generics.GenericAPIView):
    authentication_classes = []
    permission_classes = []
    serializer_class = VerifyForgotPasswordOTPSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data['email']
        otp_code = serializer.validated_data['otp']


        # 🔥 2. Get user
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({"error": "Invalid credentials"}, status=400)

        # 🔥 3. Get latest OTP
        otp = OTP.objects.filter(
            user=user,
            otp_code=otp_code,
            purpose="password_reset",
            is_used=False
        ).order_by('-created_at').first()

        if not otp:
            return Response({"error": "Invalid OTP"}, status=400)

        # 🔥 4. Check expiry
        if otp.is_expired():
            return Response({"error": "OTP expired"}, status=400)

        # 🔥 5. Mark OTP used
        otp.is_used = True
        otp.save()

        # 🔥 6. Allow password reset
        user.reset_otp_verified = True
        user.save()

        return Response(
            {"message": "OTP verified successfully"},
            status=200
        )




class ResendOTPView(mixins.CreateModelMixin, generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    

    def post(self, request):
        user = request.user

        # 🔍 get last OTP
        last_otp = OTP.objects.filter(
            user=user,
            purpose='email_verify'
        ).order_by('-created_at').first()

        # ⏱️ cooldown check (60 sec)
        if last_otp:
            diff = timezone.now() - last_otp.created_at

            if diff < timedelta(seconds=60):
                remaining = 60 - int(diff.total_seconds())
                return Response(
                    {"error": f"Wait {remaining}s before requesting new OTP"},
                    status=400
                )

        # ❌ invalidate old OTPs
        OTP.objects.filter(
            user=user,
            purpose='email_verify',
            is_used=False
        ).update(is_used=True)

        # 🔐 create new OTP
        otp_obj = create_otp(user, 'email_verify')

        send_otp_email(user.temp_email, otp_obj.otp_code)

        return Response({"message": "OTP resent successfully"}, status=200)
    




class ResetPasswordView(generics.GenericAPIView):
    authentication_classes = []
    permission_classes = []
    serializer_class = ResetPasswordSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data['email']
        new_password = serializer.validated_data['new_password']

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({"error": "Invalid credentials"}, status=400)

        if not user.reset_otp_verified:
            return Response({"error": "OTP not verified"}, status=403)

        # 🔐 Set new password
        user.set_password(new_password)
        user.reset_otp_verified = False
        user.save()

        # 🔥 Invalidate all OTPs
        OTP.objects.filter(
            user=user,
            purpose="password_reset"
        ).update(is_used=True)

        # 🚨🔥 BLACKLIST ALL REFRESH TOKENS (CORRECT WAY)
        tokens = OutstandingToken.objects.filter(user=user)
        for token in tokens:
            BlacklistedToken.objects.get_or_create(token=token)

        return Response(
            {"message": "Password reset successful"},
            status=200
        )
    



class ChangePasswordView(generics.GenericAPIView):
    serializer_class = ChangePasswordSerializer
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = request.user
        old_password = serializer.validated_data['old_password']
        new_password = serializer.validated_data['new_password']

        # ❌ wrong old password
        if not user.check_password(old_password):
            return Response(
                {"error": "Old password is incorrect"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 🔐 Set new password
        user.set_password(new_password)
        user.save()

        # 🚨🔥 BLACKLIST ALL TOKENS (FORCE LOGOUT EVERYWHERE)
        tokens = OutstandingToken.objects.filter(user=user)
        for token in tokens:
            BlacklistedToken.objects.get_or_create(token=token)

        return Response(
            {"message": "Password changed successfully"},
            status=status.HTTP_200_OK
        )

from rest_framework.decorators import action

class AddressViewSet(viewsets.ModelViewSet):
    serializer_class = AddressSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Address.objects.filter(user=self.request.user)
    def perform_create(self, serializer):
        user = self.request.user
    # ✅ if first address → make default automatically
        if not Address.objects.filter(user=user).exists():
            serializer.save(user=user, is_default=True)
            return
    # ✅ if user sets default
        if serializer.validated_data.get('is_default'):
            Address.objects.filter(user=user, is_default=True).update(is_default=False)
        serializer.save(user=user)
    def perform_update(self, serializer):
        if serializer.validated_data.get('is_default'):
            Address.objects.filter(
                user=self.request.user,
                is_default=True
            ).exclude(id=self.get_object().id).update(is_default=False)

        serializer.save()    
    def destroy(self, request, *args, **kwargs):
        address = self.get_object()

        if address.is_default:
            return Response(
                {"error": "Cannot delete default address"},
                status=400
            )

        return super().destroy(request, *args, **kwargs)    
    
    


    @action(detail=True, methods=['patch'])
    def set_default(self, request, pk=None):
        address = self.get_object()

        Address.objects.filter(
            user=request.user,
            is_default=True
        ).update(is_default=False)

        address.is_default = True
        address.save()

        return Response({
            "message": "Default address set successfully"
        })


