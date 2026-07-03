from django.urls import path
from .views import UserWalletView, AddWalletMoneyView, VerifyWalletPaymentView

urlpatterns = [
    path('', UserWalletView.as_view(), name='wallet-details'),
    path('add/', AddWalletMoneyView.as_view(), name='wallet-add-money'),
    path('verify/', VerifyWalletPaymentView.as_view(), name='wallet-verify-payment'),
]
