from rest_framework import serializers
from .models import User,Address
from django.contrib.auth import authenticate
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth.password_validation import validate_password
from .utils import StrongPasswordValidator
from allauth.socialaccount.models import SocialAccount
import re


class RegisterSerializer(serializers.ModelSerializer):
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    password = serializers.CharField(write_only=True, min_length=8)
    confirm_password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['email', 'username', 'password', 'confirm_password', 'phone', 'dob','first_name', 'last_name']

    def validate_email(self, value):
        return value.lower()

    def validate_username(self, value):
        if len(value) < 3:
            raise serializers.ValidationError("Username must be at least 3 characters")
        return value

    def validate(self, data):
        password = data['password']

        # ✅ confirm password check
        if password != data['confirm_password']:
            raise serializers.ValidationError("Passwords do not match")

        # ✅ use global validator
        StrongPasswordValidator()(password)

        return data
    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}".strip()
    
    def create(self, validated_data):
        validated_data.pop('confirm_password')  # remove extra field
        password = validated_data.pop('password')

        user = User.objects.create_user(
            password=password,
            **validated_data
        )

        return user
    


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        user = authenticate(
            username=data['email'],  # because USERNAME_FIELD = email
            password=data['password']
        )

        if not user:
            raise serializers.ValidationError("Invalid credentials")

        if not user.is_active:
            raise serializers.ValidationError("User is blocked")

        data['user'] = user  # 🔥 attach user object
        return data
 

        
class SendEmailOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()   

class VerifyEmailOTPSerializer(serializers.Serializer):
    otp = serializers.CharField(max_length=6)

class VerifyForgotPasswordOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp = serializers.CharField(max_length=6)



class ResetPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()
    new_password = serializers.CharField(min_length=8)
    confirm_password = serializers.CharField()

    def validate(self, data):
        password = data['new_password']

        # ✅ confirm password check
        if password != data['confirm_password']:
            raise serializers.ValidationError("Passwords do not match")

        # ✅ strong password validation
        StrongPasswordValidator()(password)

        return data


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True)
    confirm_password = serializers.CharField(required=True)

    def validate(self, data):
        user = self.context['request'].user
        password = data['new_password']

        # ✅ match passwords
        if password != data['confirm_password']:
            raise serializers.ValidationError("Passwords do not match")
        
        StrongPasswordValidator()(password, user)

        return data
    
class AddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = Address
        fields = '__all__'
        read_only_fields = ['user']

    def validate_phone(self, value):
        # ✅ Only digits, 10–15 length
        if not re.fullmatch(r'\d{10}', value):
            raise serializers.ValidationError("Enter a valid phone number (10 digits)")
        return value

    def validate_pincode(self, value):
        # ✅ Example: Indian pincode (6 digits)
        if not re.fullmatch(r'\d{6}', value):
            raise serializers.ValidationError("Enter a valid 6-digit pincode")
        return value

    def validate_city(self, value):
        if not re.fullmatch(r'[A-Za-z ]+', value):
            raise serializers.ValidationError("City must contain only letters and spaces")
        return value.title().strip()

    def validate_state(self, value):
        if not re.fullmatch(r'[A-Za-z ]+', value):
            raise serializers.ValidationError("State must contain only letters")
        return value.title().strip()

    def validate(self, data):
        # ✅ get existing value if not provided in PATCH
        address_line = data.get('address_line') or getattr(self.instance, 'address_line', '')

        if len(address_line) < 10:
            raise serializers.ValidationError("Address is too short")

        return data

   
class ProfileSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    is_social = serializers.SerializerMethodField()
    addresses = AddressSerializer(many=True, read_only=True)
    joined_date = serializers.DateTimeField(source='date_joined', read_only=True)

    class Meta:
        model = User
        fields = ['email',
                   'username', 
                   'first_name',
                   'last_name',
                   'phone', 
                   'full_name',
                   'dob',
                   'is_gold_member',
                   'joined_date',
                   'addresses',
                   'is_social',
                   'is_verified']

    def update(self, instance, validated_data):
        new_email = validated_data.get('email', instance.email)

        # 🔥 check if email changed
        if instance.email != new_email:
            instance.is_verified = False  # ❗ reset verification

        return super().update(instance, validated_data)
    
    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}".strip()

    def get_is_social(self, obj):
        return SocialAccount.objects.filter(user=obj).exists()
