from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.core.validators import RegexValidator
from django.conf import settings
from django.utils import timezone

#  Custom User Manager
class UserManager(BaseUserManager):
    def create_user(self, email, username, password=None, **extra_fields):
        if not email:
            raise ValueError("Email is required")

        email = self.normalize_email(email)

        user = self.model(
            email=email,
            username=username,
            **extra_fields
        )

        user.set_password(password)  # 🔐 hash password
        user.save(using=self._db)
        return user

    def create_superuser(self, email, username, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError("Superuser must have is_staff=True")
        if extra_fields.get('is_superuser') is not True:
            raise ValueError("Superuser must have is_superuser=True")

        return self.create_user(email, username, password, **extra_fields)


#  Custom User Model
class User(AbstractUser):

    # ✅ keep username (for display)
    username = models.CharField(max_length=150, unique=True)

    # ✅ use email for login
    email = models.EmailField(unique=True, db_index=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    # 🔥 attach manager
    objects = UserManager()

    phone = models.CharField(
    max_length=15,
    unique=True,
    validators=[RegexValidator(r'^\+?\d{10,15}$', "Enter valid phone number")],
    null=True,
    blank=True
)

    # 🔹 custom fields
    dob = models.DateField(null=True, blank=True)

    role = models.CharField(
        max_length=20,
        choices=[
            ('user', 'User'),
            ('admin', 'Admin'),
        ],
        default='user'
    )

    # ✅ use built-in auth control
    is_active = models.BooleanField(default=True)
    temp_email = models.EmailField(null=True, blank=True)

    is_verified = models.BooleanField(default=False)
    reset_otp_verified = models.BooleanField(default=False)

    is_gold_member = models.BooleanField(default=False)
    gold_purchased_at = models.DateTimeField(null=True, blank=True)

    # 🔹 timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    def save(self, *args, **kwargs):
        if self.phone == "":
            self.phone = None
        super().save(*args, **kwargs)

    def __str__(self):
        return self.email
    



class OTP(models.Model):

    PURPOSE_CHOICES = [
        ('email_verify', 'Email Verify'),
        ('password_reset', 'Password Reset'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    otp_code = models.CharField(max_length=6)
    purpose = models.CharField(max_length=20, choices=PURPOSE_CHOICES)

    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    def is_expired(self):
        return timezone.now() > self.expires_at   

        


class Address(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="addresses")
    
    full_name = models.CharField(max_length=100)
    phone = models.CharField(max_length=15)

    address_line = models.TextField()
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    pincode = models.CharField(max_length=10)
    country=models.CharField(max_length=50)

    is_default = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.full_name} - {self.city}"        