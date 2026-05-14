from django.shortcuts import render

# Create your views here.
from rest_framework import generics, mixins
from .models import User,OTP
from django.utils import timezone
from .serializers import RegisterSerializer,LoginSerializer,ProfileSerializer,LogoutSerializer,SendEmailOTPSerializer,VerifyEmailOTPSerializer
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
                "phone": user.phone
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

class ForgotPasswordView(generics.GenericAPIView):
    def post(self, request):
        email = request.data.get('email')

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=404)

        otp_obj = create_otp(user, 'password_reset')

        print("OTP:", otp_obj.otp_code)

        return Response({"message": "OTP sent"})  
    
class ResetPasswordView(generics.GenericAPIView):
    def post(self, request):
        email = request.data.get('email')
        otp_code = request.data.get('otp')
        new_password = request.data.get('password')

        try:
            user = User.objects.get(email=email)

            otp = OTP.objects.filter(
                user=user,
                otp_code=otp_code,
                purpose='password_reset',
                is_used=False
            ).latest('created_at')

        except:
            return Response({"error": "Invalid OTP"}, status=400)

        if otp.is_expired():
            return Response({"error": "OTP expired"}, status=400)

        # ✅ reset password
        user.set_password(new_password)
        user.save()

        otp.is_used = True
        otp.save()

        return Response({"message": "Password reset successful"})    
