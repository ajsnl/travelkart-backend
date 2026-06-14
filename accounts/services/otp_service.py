from django.utils import timezone
from datetime import timedelta
from rest_framework.exceptions import ValidationError
from accounts.models import User, OTP
from accounts.utils import create_otp, send_otp_email

class OtpService:
    @staticmethod
    def send_email_otp(user, email=None):
        """Sends an OTP to the user's email or a new email for verification."""
        # CASE 1: Email update
        if email:
            if User.objects.filter(email=email).exclude(id=user.id).exists():
                raise ValidationError({"error": "Email already in use"})

            user.temp_email = email
            user.is_verified = False

        # CASE 2: Signup verification
        else:
            if not user.email:
                raise ValidationError({"error": "No email found"})

            user.temp_email = user.email

        user.save()

        otp_obj = create_otp(user, 'email_verify')
        send_otp_email(user.temp_email, otp_obj.otp_code)
        return {"message": "OTP sent to email"}

    @staticmethod
    def verify_email_otp(user, otp_code):
        """Verifies the OTP code for email verification and updates the user's email."""
        if not otp_code:
            raise ValidationError({"error": "OTP is required"})

        otp = OTP.objects.filter(
            user=user,
            otp_code=otp_code,
            purpose='email_verify',
            is_used=False
        ).order_by('-created_at').first()

        if not otp:
            raise ValidationError({"error": "Invalid OTP"})

        if otp.expires_at < timezone.now():
            raise ValidationError({"error": "OTP expired"})

        if not user.temp_email:
            raise ValidationError({"error": "No email to verify"})

        if User.objects.filter(email=user.temp_email).exclude(id=user.id).exists():
            raise ValidationError({"error": "Email already in use"})

        # mark OTP used
        otp.is_used = True
        otp.save()

        # update email safely
        user.email = user.temp_email
        user.temp_email = None
        user.is_verified = True
        user.save()
        return {"message": "Email verified successfully"}

    @staticmethod
    def resend_email_otp(user):
        """Resends the email verification OTP with cooldown check."""
        if not user.temp_email:
            raise ValidationError({"error": "No email to verify"})

        last_otp = OTP.objects.filter(
            user=user,
            purpose='email_verify'
        ).order_by('-created_at').first()

        if last_otp:
            diff = timezone.now() - last_otp.created_at
            if diff < timedelta(seconds=60):
                remaining = 60 - int(diff.total_seconds())
                raise ValidationError({"error": f"Wait {remaining}s before requesting new OTP"})

        OTP.objects.filter(
            user=user,
            purpose='email_verify',
            is_used=False
        ).update(is_used=True)

        otp_obj = create_otp(user, 'email_verify')
        send_otp_email(user.temp_email, otp_obj.otp_code)
        return {"message": "OTP resent successfully"}
