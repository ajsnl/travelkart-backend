import random
from datetime import timedelta
from django.utils import timezone
from .models import OTP


def generate_otp():
    return str(random.randint(100000, 999999))


def create_otp(user, purpose):
    otp = generate_otp()

    return OTP.objects.create(
        user=user,
        otp_code=otp,
        purpose=purpose,
        expires_at=timezone.now() + timedelta(minutes=5)
    )

import re
from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password


class StrongPasswordValidator:
    def __call__(self, password, user=None):
        # ✅ Django built-in validation
        validate_password(password, user)

        # ✅ Custom rules
        if not re.search(r'[A-Z]', password):
            raise serializers.ValidationError("Password must contain at least 1 uppercase letter")

        if not re.search(r'[a-z]', password):
            raise serializers.ValidationError("Password must contain at least 1 lowercase letter")

        if not re.search(r'[0-9]', password):
            raise serializers.ValidationError("Password must contain at least 1 number")

        if not re.search(r'[!@#$%^&*(),.?\":{}|<>]', password):
            raise serializers.ValidationError("Password must contain at least 1 special character")