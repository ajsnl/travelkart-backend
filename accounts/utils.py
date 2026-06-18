import random
from datetime import timedelta
from django.utils import timezone
from .models import OTP
from django.core.mail import send_mail
from django.conf import settings


def generate_otp():
    return str(random.randint(100000, 999999))


def create_otp(user, purpose):
    otp = generate_otp()

    return OTP.objects.create(
        user=user,
        otp_code=otp,
        purpose=purpose,
        expires_at=timezone.now() + timedelta(minutes=1)
    )



def send_otp_email(email, otp):
    subject = "TravelKart OTP Verification Code"
    message = (
        f"Hello,\n\n"
        f"Thank you for choosing TravelKart.\n\n"
        f"Your One-Time Password (OTP) is:\n"
        f"{otp}\n\n"
        f"This code is valid for the next 1 minute. Please do not share this code with anyone for security reasons.\n\n"
        f"If you did not request this code, please ignore this email or contact our support team immediately.\n\n"
        f"Best regards,\n"
        f"TravelKart Team"
    )

    send_mail(
        subject,
        message,
        settings.EMAIL_HOST_USER,
        [email],
        fail_silently=False,
    )

import re
from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password


class StrongPasswordValidator:
    def __call__(self, password, user=None):
        #  Django built-in validation
        validate_password(password, user)

        #  Custom rules
        if not re.search(r'[A-Z]', password):
            raise serializers.ValidationError("Password must contain at least 1 uppercase letter")

        if not re.search(r'[a-z]', password):
            raise serializers.ValidationError("Password must contain at least 1 lowercase letter")

        if not re.search(r'[0-9]', password):
            raise serializers.ValidationError("Password must contain at least 1 number")

        if not re.search(r'[!@#$%^&*(),.?\":{}|<>]', password):
            raise serializers.ValidationError("Password must contain at least 1 special character")