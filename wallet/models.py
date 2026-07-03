from django.db import models
from django.conf import settings

# Create your models here.
class Wallet(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="wallet")
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0)

class WalletTransaction(models.Model):
    TRANSACTION_TYPE = (
        ("CREDIT", "Credit"),
        ("DEBIT", "Debit"),
    )

    STATUS_CHOICES = (
        ("pending", "Pending"),
        ("success", "Success"),
        ("failed", "Failed"),
    )

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    transaction_type = models.CharField(max_length=10, choices=TRANSACTION_TYPE)
    reason = models.CharField(max_length=255)  # refund, add money, purchase
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="success")
    razorpay_order_id = models.CharField(max_length=100, blank=True, null=True)
    razorpay_payment_id = models.CharField(max_length=100, blank=True, null=True)
    razorpay_signature = models.CharField(max_length=200, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
