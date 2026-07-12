from django.urls import path,include
from .views import RegisterView,LoginView,ProfileView,LogoutView,SendEmailOTPView,ResetPasswordView,VerifyEmailOTPView,ForgotPasswordView,UploadProfilePicture
from .views import ResendOTPView,ForgotPasswordVerifyOTPView,ChangePasswordView,AddressViewSet,RefreshView,UserMeView,get_csrf_token,GoogleLogin,GoldMembership,ReferralStatsView
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
    path('upload-profile/', UploadProfilePicture.as_view()),
    path('referrals/',ReferralStatsView.as_view(),name='referral_stats'),

    # dj-rest-auth endpoints 
    path('dj-rest-auth/', include('dj_rest_auth.urls')),
    path('dj-rest-auth/registration/', include('dj_rest_auth.registration.urls')),

    #  Google OAuth
    path('social/', include('allauth.socialaccount.urls')),
    path('google/', GoogleLogin.as_view(), name='google_login'),
    path('gold-membership/',GoldMembership.as_view(),name='gold_membership')
]




urlpatterns += router.urls