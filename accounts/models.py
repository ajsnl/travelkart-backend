from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.core.validators import RegexValidator

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

    is_verified = models.BooleanField(default=False)

    is_gold_member = models.BooleanField(default=False)
    gold_purchased_at = models.DateTimeField(null=True, blank=True)

    # 🔹 timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.email