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