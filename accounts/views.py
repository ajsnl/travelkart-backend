from django.shortcuts import render
from datetime import timedelta
from rest_framework import generics, mixins, viewsets, status
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser, FormParser
from django.http import JsonResponse
from django.views.decorators.csrf import ensure_csrf_cookie
from django.contrib.auth import get_user_model
from rest_framework.exceptions import ValidationError


from allauth.socialaccount.providers.google.views import GoogleOAuth2Adapter
from dj_rest_auth.registration.views import SocialLoginView

from .models import User, OTP, Address,Referral,SignupOTP
from .serializers import (
    RegisterSerializer, LoginSerializer, ProfileSerializer,
    SendEmailOTPSerializer, VerifyEmailOTPSerializer,
    VerifyForgotPasswordOTPSerializer, ResetPasswordSerializer,
    ChangePasswordSerializer, AddressSerializer, ProfilePictureUploadSerializer
)
from .utils import generate_otp
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
            return Response({"error": "Your session has expired. Please log in again."}, status=status.HTTP_401_UNAUTHORIZED)

        try:
            new_access, new_refresh = AuthService.refresh_tokens(refresh_token)
            response = Response({"message": "Token refreshed"})
            AuthService.set_auth_cookies(response, new_access, new_refresh)
            return response
        except Exception:
            return Response({"error": "Your session has expired. Please log in again."}, status=status.HTTP_401_UNAUTHORIZED)


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
    authentication_classes=[]

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


class SendSignupOTPView(APIView):
    authentication_classes = []
    permission_classes = []
    def post(self, request):
        email = request.data.get('email')
        if not email:
            raise ValidationError({"email": ["Email is required"]})
        email = email.strip().lower()
        # Validate email is not in use
        if User.objects.filter(email=email).exists():
            raise ValidationError({"email": ["Email is already registered"]})
        # Enforce 60s cooldown
        last_otp = SignupOTP.objects.filter(email=email).first()
        if last_otp:
            diff = timezone.now() - last_otp.created_at
            if diff < timedelta(seconds=60):
                remaining = 60 - int(diff.total_seconds())
                raise ValidationError({"error": f"Wait {remaining}s before requesting new OTP"})
        otp_code = generate_otp()
        expires_at = timezone.now() + timedelta(minutes=5)
        # Delete any existing OTP for this email to reset state
        SignupOTP.objects.filter(email=email).delete()
        SignupOTP.objects.create(
            email=email,
            otp_code=otp_code,
            expires_at=expires_at,
            is_verified=False
        )
        # Send email
        subject = "TravelKart Signup Verification Code"
        message = (
            f"Hello,\n\n"
            f"Thank you for choosing TravelKart.\n\n"
            f"Your One-Time Password (OTP) for registration is:\n"
            f"{otp_code}\n\n"
            f"This code is valid for the next 5 minutes. Please do not share this code with anyone for security reasons.\n\n"
            f"If you did not request this code, please ignore this email.\n\n"
            f"Best regards,\n"
            f"TravelKart Team"
        )
        try:
            from django.core.mail import send_mail
            from django.conf import settings
            send_mail(
                subject,
                message,
                settings.EMAIL_HOST_USER,
                [email],
                fail_silently=False,
            )
        except Exception as e:
            # Delete the newly created OTP record so the user is not locked by the 60s cooldown on failure
            SignupOTP.objects.filter(email=email).delete()
            raise ValidationError({"error": "Failed to send verification email. Please check your connection or try again."})
        return Response({"message": "OTP sent to email"}, status=status.HTTP_200_OK)
class VerifySignupOTPView(APIView):
    authentication_classes = []
    permission_classes = []
    def post(self, request):
        email = request.data.get('email')
        otp_code = request.data.get('otp')
        if not email or not otp_code:
            raise ValidationError({"error": "Email and OTP code are required"})
        email = email.strip().lower()
        otp_code = otp_code.strip()
        try:
            signup_otp = SignupOTP.objects.get(email=email)
        except SignupOTP.DoesNotExist:
            raise ValidationError({"error": "No OTP verification request found for this email"})
        if signup_otp.is_expired():
            raise ValidationError({"error": "OTP has expired. Please request a new one"})
        if signup_otp.otp_code != otp_code:
            raise ValidationError({"error": "Invalid OTP code"})
        signup_otp.is_verified = True
        signup_otp.save()
        return Response({"message": "Email verified successfully"}, status=status.HTTP_200_OK)


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

from django.conf import settings 
from django.utils import timezone  
import requests 
import random
import base64
import hmac
import hashlib

class GoldMembership(APIView):
    permission_classes=[IsAuthenticated]

    def patch(self,request):
        user=request.user
        if user.is_gold_member:
            raise ValidationError({"error": "You are already a Gold Member."})
        
        key_id=getattr(settings,'RAZORPAY_KEY_ID',None)
        key_secret=getattr(settings,'RAZORPAY_KEY_SECRET',None)
        if not key_id or not key_secret or key_id.startswith('dummy') or key_secret.startswith('dummy'):
            raise ValidationError({"error": "Razorpay payment credentials are not configured on the server. Please contact support."})
        
        try:
            auth_str = f"{key_id}:{key_secret}"
            base64_auth = base64.b64encode(auth_str.encode('ascii')).decode('ascii')
            headers = {
                "Authorization": f"Basic {base64_auth}",
                "Content-Type": "application/json"
            }
            receipt = f"GOLD-{user.id}-{random.randint(100000, 999999)}"
            payload = {
                "amount": 149900,
                "currency": "INR",
                "receipt": receipt
            }
            response = requests.post("https://api.razorpay.com/v1/orders", headers=headers, json=payload, timeout=10)
            if response.status_code in [200, 201]:
                razorpay_order_id = response.json().get('id')
                return Response({
                    "razorpay_order_id": razorpay_order_id,
                    "amount": 1499,
                    "currency": "INR",
                    "razorpay_key_id": key_id
                })          
            else:
                raise ValidationError({"error": f"Razorpay order initialization failed with status {response.status_code}: {response.text}"})
        except requests.RequestException as e:
            raise ValidationError({"error": f"Network error connecting to Razorpay: {str(e)}"})
        except ValidationError:
            raise
        except Exception as e:
            raise ValidationError({"error": f"An error occurred: {str(e)}"})
        
    def post(self,request):
        user=request.user
        razorpay_payment_id = request.data.get('razorpay_payment_id')
        razorpay_order_id = request.data.get('razorpay_order_id')
        razorpay_signature = request.data.get('razorpay_signature')
        if not all([razorpay_payment_id, razorpay_order_id, razorpay_signature]):
            raise ValidationError({"error": "razorpay_payment_id, razorpay_order_id, and razorpay_signature are required."})
        key_id = getattr(settings, 'RAZORPAY_KEY_ID', None)
        key_secret = getattr(settings, 'RAZORPAY_KEY_SECRET', None)
        if not key_secret or key_secret == 'dummy_key_secret':
            raise ValidationError({"error": "Razorpay credentials are not configured on the server."})
        # Verify payment signature using HMAC-SHA256
        msg = f"{razorpay_order_id}|{razorpay_payment_id}"
        generated_signature = hmac.new(
            key=key_secret.encode('utf-8'),
            msg=msg.encode('utf-8'),
            digestmod=hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(generated_signature, razorpay_signature):
            raise ValidationError({"error": "Payment signature verification failed."})
        # Fetch order details from Razorpay to verify receipt intent and amount
        try:
            auth_str = f"{key_id}:{key_secret}"
            base64_auth = base64.b64encode(auth_str.encode('ascii')).decode('ascii')
            headers = {
                "Authorization": f"Basic {base64_auth}",
                "Content-Type": "application/json"
            }
            response = requests.get(f"https://api.razorpay.com/v1/orders/{razorpay_order_id}", headers=headers, timeout=10)
            if response.status_code == 200:
                order_details = response.json()
                receipt = order_details.get("receipt", "")
                amount = order_details.get("amount", 0)
                
                # Check that receipt aligns with user id and starts with GOLD
                expected_receipt_prefix = f"GOLD-{user.id}-"
                if not receipt.startswith(expected_receipt_prefix):
                    raise ValidationError({"error": "This payment order was not created for your Gold Membership purchase."})
                
                # Check that amount paid matches the membership cost (₹1,499 in paise)
                if amount != 149900:
                    raise ValidationError({"error": "Incorrect payment amount for Gold Membership."})
            else:
                raise ValidationError({"error": f"Failed to retrieve order details from Razorpay: status {response.status_code}"})
        except requests.RequestException as e:
            raise ValidationError({"error": f"Network error connecting to Razorpay to verify order details: {str(e)}"})
        # Everything verified! Activate Gold Membership
        user.is_gold_member = True
        user.gold_purchased_at = timezone.now()
        user.save()
        return Response({
            "status": "success",
            "message": "Successfully upgraded to Gold Membership."
        })


class ReferralStatsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        
        # Ensure referral code is generated
        if not user.referral_code:
            import uuid
            code = str(uuid.uuid4())[:8].upper()
            while User.objects.filter(referral_code=code).exists():
                code = str(uuid.uuid4())[:8].upper()
            user.referral_code = code
            user.save(update_fields=['referral_code'])

        frontend_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:5173')
        referral_url = f"{frontend_url}/signup?ref={user.referral_code}"
        
        # Query referrals sent by this user
        referrals_query = Referral.objects.filter(referrer=user).select_related('referred_user')
        
        referrals_list = []
        total_earned = 0
        gold_days_earned = 0
        for ref in referrals_query:
            status_display = ref.get_status_display()
            is_rewarded = ref.status == 'rewarded'
            
            referrals_list.append({
                "id": ref.id,
                "email": ref.referred_user.email,
                "username": ref.referred_user.username,
                "status": ref.status,  # signed_up, first_order, rewarded
                "status_display": status_display,
                "created_at": ref.created_at,
                "rewarded_at": ref.rewarded_at,
            })
            
            if is_rewarded:
                total_earned += 99
                gold_days_earned += 3

        # Check if this user was referred and rewarded
        try:
            incoming_referral = Referral.objects.get(referred_user=user)
            if incoming_referral.status == 'rewarded':
                total_earned += 50
        except Referral.DoesNotExist:
            pass    

        return Response({
            "referral_code": user.referral_code,
            "referral_url": referral_url,
            "total_earned": total_earned,
            "gold_days_earned": gold_days_earned,
            "referrals": referrals_list
        })




