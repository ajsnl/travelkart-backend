from django.urls import path
from .views import RegisterView,LoginView,ProfileView,LogoutView,SendEmailOTPView,ResetPasswordView,VerifyEmailOTPView,ForgotPasswordView
from .views import ResendOTPView,ForgotPasswordVerifyOTPView,ChangePasswordView,AddressViewSet,RefreshView,UserMeView,get_csrf_token
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register(r'addresses', AddressViewSet, basename='addresses')

urlpatterns = [
    path('signup/', RegisterView.as_view(), name='signup'),
    path('login/',LoginView.as_view(),name='login'),
    path('profile/',ProfileView.as_view(),name='profile'),
    path('logout/',LogoutView.as_view(),name='logout'),
    path('send-email-otp/', SendEmailOTPView.as_view()),
    path('verify-email-otp/', VerifyEmailOTPView.as_view()),
    path('forgot-password/', ForgotPasswordView.as_view()),
    path('verify-forgot-otp/',ForgotPasswordVerifyOTPView.as_view()),
    path('reset-password/', ResetPasswordView.as_view()),
    path('resend-otp/',ResendOTPView.as_view()),
    path('change-password/',ChangePasswordView.as_view()),
    path("refresh/", RefreshView.as_view(), name="token_refresh"),
    path("user/me/", UserMeView.as_view()),
    path("csrf/", get_csrf_token),
]




urlpatterns += router.urls