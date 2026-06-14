from django.utils import timezone
from datetime import timedelta
from rest_framework.exceptions import ValidationError, NotFound, PermissionDenied
from django.contrib.auth import get_user_model
from accounts.models import OTP
from accounts.utils import create_otp, send_otp_email
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken, BlacklistedToken

User = get_user_model()

class PasswordService:
    @staticmethod
    def send_forgot_password_otp(email):
        """Validates user and sends password reset OTP code if eligible."""
        if not email:
            raise ValidationError({"error": "Email is required"})

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise NotFound({"error": "User not found"})

        # Cooldown check (60 sec)
        last_otp = OTP.objects.filter(
            user=user,
            purpose="password_reset"
        ).order_by('-created_at').first()

        if last_otp and (timezone.now() - last_otp.created_at).seconds < 60:
            raise ValidationError({"error": "Please wait before requesting another OTP"})

        # Invalidate old OTPs
        OTP.objects.filter(
            user=user,
            purpose="password_reset",
            is_used=False
        ).update(is_used=True)

        # Create new OTP
        otp_obj = create_otp(user, "password_reset")
        send_otp_email(user.email, otp_obj.otp_code)
        return {"message": "OTP sent successfully"}

    @staticmethod
    def verify_forgot_password_otp(email, otp_code):
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise ValidationError({"error": "Invalid credentials"})

        otp = OTP.objects.filter(
            user=user,
            otp_code=otp_code,
            purpose="password_reset",
            is_used=False
        ).order_by('-created_at').first()

        if not otp:
            raise ValidationError({"error": "Invalid OTP"})

        if otp.is_expired():
            raise ValidationError({"error": "OTP expired"})

        otp.is_used = True
        otp.save()

        user.reset_otp_verified = True
        user.save()
        return {"message": "OTP verified successfully"}

    @staticmethod
    def reset_password(email, new_password):
        """Resets user password and invalidates tokens."""
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise ValidationError({"error": "Invalid credentials"})

        if not user.reset_otp_verified:
            raise PermissionDenied({"error": "OTP not verified"})

        user.set_password(new_password)
        user.reset_otp_verified = False
        user.save()

        OTP.objects.filter(
            user=user,
            purpose="password_reset"
        ).update(is_used=True)

        # Blacklist all tokens
        tokens = OutstandingToken.objects.filter(user=user)
        for token in tokens:
            BlacklistedToken.objects.get_or_create(token=token)

        return {"message": "Password reset successful"}

    @staticmethod
    def change_password(user, old_password, new_password):
        if not user.check_password(old_password):
            raise ValidationError({"error": "Old password is incorrect"})

        user.set_password(new_password)
        user.save()

        # Blacklist all tokens
        tokens = OutstandingToken.objects.filter(user=user)
        for token in tokens:
            BlacklistedToken.objects.get_or_create(token=token)

        return {"message": "Password changed successfully"}
