from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.db.models import Sum
from products.models import Product

def recalculate_product_sales(product):
    if not product:
        return
    from orders.models import OrderItem
    sales_sum = OrderItem.objects.filter(
        variant__product=product,
        order__payment_status='paid',
        is_cancelled=False,
        is_returned=False
    ).aggregate(total=Sum('quantity'))['total']
    
    product.total_sales = sales_sum or 0
    product.save(update_fields=['total_sales'])

@receiver(post_save, sender='orders.OrderItem')
def update_product_sales_on_item_save(sender, instance, **kwargs):
    if instance.variant and instance.variant.product:
        recalculate_product_sales(instance.variant.product)

@receiver(post_delete, sender='orders.OrderItem')
def update_product_sales_on_item_delete(sender, instance, **kwargs):
    if instance.variant and instance.variant.product:
        recalculate_product_sales(instance.variant.product)

@receiver(post_save, sender='orders.Order')
def update_product_sales_on_order_save(sender, instance, **kwargs):
    # Recalculate sales for all products in this order
    for item in instance.items.all():
        if item.variant and item.variant.product:
            recalculate_product_sales(item.variant.product)
