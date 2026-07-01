from django.db import models

# Create your models here.

class Coupon(models.Model):
    code = models.CharField(max_length=50, unique=True)
    discount_type = models.CharField(
        choices=[("PERCENT", "Percent"), ("FLAT", "Flat")],
        max_length=10
    )
    discount_value = models.IntegerField()
    min_order_amount = models.IntegerField(default=0)
    max_discount = models.IntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    valid_from = models.DateTimeField()
    valid_to = models.DateTimeField()
    usage_limit=models.IntegerField(null=True)
    used_count=models.IntegerField(default=0)

