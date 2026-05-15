from django.urls import path
from .views import RegisterView,LoginView,ProfileView,LogoutView,SendEmailOTPView,ResetPasswordView,VerifyEmailOTPView,ForgotPasswordView
from .views import ResendOTPView,ForgotPasswordVerifyOTPView,ChangePasswordView
urlpatterns = [
    path('signup/', RegisterView.as_view(), name='signup'),
    path('login/',LoginView.as_view(),name='login'),
    path('profile/',ProfileView.as_view(),name='profile'),
    path('logout/',LogoutView.as_view(),name='logout'),
    path('send-email-otp/', SendEmailOTPView.as_view()),
    path('verify-email-otp/', VerifyEmailOTPView.as_view()),
    path('forgot-password/', ForgotPasswordView.as_view()),
    path('verify-forget-otp/',ForgotPasswordVerifyOTPView.as_view()),
    path('reset-password/', ResetPasswordView.as_view()),
    path('resend-otp/',ResendOTPView.as_view()),
    path('change-password/',ChangePasswordView.as_view()),
]