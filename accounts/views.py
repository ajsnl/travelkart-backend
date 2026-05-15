from django.shortcuts import render

# Create your views here.
from rest_framework import generics, mixins
from .models import User,OTP
from django.utils import timezone
from django.contrib.auth import get_user_model
from datetime import timedelta
from .serializers import RegisterSerializer,LoginSerializer,ProfileSerializer,LogoutSerializer,SendEmailOTPSerializer,VerifyEmailOTPSerializer,VerifyForgotPasswordOTPSerializer,ResetPasswordSerializer
from .serializers import ChangePasswordSerializer
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .serializers import LoginSerializer
from rest_framework import status
from .utils import create_otp
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
                "phone": user.phone,
                "is_verified": user.is_verified
            },
            "refresh": str(refresh),
            "access": str(refresh.access_token),
        }, status=status.HTTP_200_OK)
    

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
    


class LogoutView(mixins.CreateModelMixin, generics.GenericAPIView):
    serializer_class = LogoutSerializer
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response({"message": "Logged out successfully"}, status=status.HTTP_205_RESET_CONTENT)    
    





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

        print("OTP:", otp_obj.otp_code)  # for testing

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

        print("OTP:", otp_obj.otp_code)

        return Response({"message": "OTP sent successfully"}, status=200)
    


User = get_user_model()

class ForgotPasswordVerifyOTPView(generics.GenericAPIView):
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

        print("RESEND OTP:", otp_obj.otp_code)

        return Response({"message": "OTP resent successfully"}, status=200)
    
class ResetPasswordView(generics.GenericAPIView):
    serializer_class = ResetPasswordSerializer


    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data['email']
        new_password = serializer.validated_data['new_password']



        # 🔥 2. Get user
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({"error": "Invalid credentials"}, status=400)

        # 🔥 3. Check OTP verified
        if not user.reset_otp_verified:
            return Response(
                {"error": "OTP not verified"},
                status=403
            )

        # 🔥 4. Reset password
        user.set_password(new_password)

        # 🔥 5. Reset flag (VERY IMPORTANT)
        user.reset_otp_verified = False
        user.save()

        # 🔥 6. Invalidate any remaining OTPs
        OTP.objects.filter(
            user=user,
            purpose="password_reset",
            is_used=False
        ).update(is_used=True)

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

        # ✅ check old password
        if not user.check_password(old_password):
            return Response(
                {"error": "Old password is incorrect"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # ✅ set new password
        user.set_password(new_password)
        user.save()

        return Response(
            {"message": "Password changed successfully"},
            status=status.HTTP_200_OK
        )    
