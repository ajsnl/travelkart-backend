from rest_framework import serializers
from .models import User
from django.contrib.auth import authenticate
from rest_framework_simplejwt.tokens import RefreshToken


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=6)

    class Meta:
        model = User
        fields = ['email', 'username', 'password', 'phone', 'dob']

    def validate_email(self, value):
        return value.lower()

    def validate_username(self, value):
        if len(value) < 3:
            raise serializers.ValidationError("Username must be at least 3 characters")
        return value

    def create(self, validated_data):
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
    
class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['email', 'username', 'phone', 'dob']

    def update(self, instance, validated_data):
        new_email = validated_data.get('email', instance.email)

        # 🔥 check if email changed
        if instance.email != new_email:
            instance.is_verified = False  # ❗ reset verification

        return super().update(instance, validated_data)




class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField()

    def validate(self, data):
        self.token = data['refresh']
        return data

    def save(self):
        try:
            token = RefreshToken(self.token)
            token.blacklist()  # 🔥 blacklist token
        except Exception:
            raise serializers.ValidationError("Invalid or expired token")
        
class SendEmailOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()   

class VerifyEmailOTPSerializer(serializers.Serializer):
    otp = serializers.CharField()    
