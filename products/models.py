from django.db import models

# Create your models here.
class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)
    
    # Self-referencing FK for sub-categories
    parent = models.ForeignKey(
        'self', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='subcategories'
    )

    # Category level offers
    offer_type = models.CharField(
        max_length=20,
        choices=[
            ('none', 'No Offer'),
            ('percentage', 'Percentage Discount'),
            ('flat', 'Flat Discount')
        ],
        default='none'
    )
    offer_value = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    max_discount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    min_product_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    expiry_date = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.parent.name} > {self.name}" if self.parent else self.name


class Product(models.Model):
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    short_description = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True) # Full description
    
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name='products')
    brand = models.CharField(max_length=100, blank=True)
    
    # Status, Visibility, Shipping
    is_active = models.BooleanField(default=False)
    is_featured = models.BooleanField(default=False)
    free_delivery = models.BooleanField(default=False)
    est_delivery_time = models.CharField(max_length=100, blank=True) 
    
    # Global attributes (e.g. {"material": "polycarbonate", "warranty": "2 years"})
    attributes = models.JSONField(default=dict, blank=True)
    
    # Ratings 
    average_rating = models.FloatField(default=0.0)
    total_reviews = models.IntegerField(default=0)

    def update_rating_stats(self):
        from reviews.models import Review
        # Only active reviews count
        active_reviews = Review.objects.filter(product=self, is_active=True)
        stats = active_reviews.aggregate(
            avg_rating=models.Avg('rating'),
            total_count=models.Count('id')
        )
        self.average_rating = stats['avg_rating'] or 0.0
        self.total_reviews = stats['total_count'] or 0
        self.save(update_fields=['average_rating', 'total_reviews'])
    
    # Sales
    total_sales = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class ProductVariant(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='variants')
    sku = models.CharField(max_length=100, unique=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stock = models.PositiveIntegerField(default=0)
    
    # Variant attributes (e.g. {"color": "Charcoal", "capacity": "20L", "size": "S"})
    attributes = models.JSONField(default=dict)
    is_active = models.BooleanField(default=False)
    
    # Variant level offers
    offer_type = models.CharField(
        max_length=20,
        choices=[
            ('none', 'No Offer'),
            ('percentage', 'Percentage Discount'),
            ('flat', 'Flat Discount')
        ],
        default='none'
    )
    offer_value = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def get_effective_offer(self):
        """
        Returns a dict with details of the best active offer for this variant:
        {
            'offer_type': 'none' | 'percentage' | 'flat',
            'offer_value': Decimal,
            'discount_amount': Decimal,
            'offer_price': Decimal,
            'source': 'variant' | 'category' | 'parent_category' | 'none'
        }
        """
        from django.utils import timezone
        from decimal import Decimal
        
        now = timezone.now()
        price = Decimal(str(self.price))
        best_discount = Decimal('0.00')
        best_offer_type = 'none'
        best_offer_value = Decimal('0.00')
        source = 'none'
        # 1. Evaluate Variant's own offer
        if self.offer_type != 'none' and self.offer_value > 0:
            val = Decimal(str(self.offer_value))
            if self.offer_type == 'percentage':
                v_discount = price * (val / Decimal('100.00'))
            else: # flat
                v_discount = val
            if v_discount > best_discount:
                best_discount = v_discount
                best_offer_type = self.offer_type
                best_offer_value = val
                source = 'variant'
        # Helper to check category offer
        def evaluate_category_offer(category, category_source):
            nonlocal best_discount, best_offer_type, best_offer_value, source
            if not category or not category.is_active or category.is_deleted:
                return
            
            # Check if category offer is valid
            if category.offer_type == 'none' or category.offer_value <= 0:
                return
            
            # Check expiry date
            if category.expiry_date and category.expiry_date < now:
                return
            
            # Avoid misuse on cheap products (min_product_price check)
            if category.min_product_price and price < Decimal(str(category.min_product_price)):
                return
            
            # Calculate discount
            cat_val = Decimal(str(category.offer_value))
            if category.offer_type == 'percentage':
                c_discount = price * (cat_val / Decimal('100.00'))
                if category.max_discount and category.max_discount > 0:
                    c_discount = min(c_discount, Decimal(str(category.max_discount)))
            else: # flat
                c_discount = cat_val
                
            if c_discount > best_discount:
                best_discount = c_discount
                best_offer_type = category.offer_type
                best_offer_value = cat_val
                source = category_source
        # 2. Evaluate Category's offer
        category = self.product.category
        evaluate_category_offer(category, 'category')
        # 3. Evaluate Parent Category's offer
        if category and category.parent:
            evaluate_category_offer(category.parent, 'parent_category')
        # Round discount to 2 decimal places
        best_discount = best_discount.quantize(Decimal('0.01'))
        offer_price = max(Decimal('0.00'), price - best_discount)
        return {
            'offer_type': best_offer_type,
            'offer_value': best_offer_value,
            'discount_amount': best_discount,
            'offer_price': offer_price,
            'source': source
        }
    @classmethod
    def get_effective_price_expression(cls, prefix=''):
        from django.db.models import Case, When, F, Q, DecimalField, Value, ExpressionWrapper
        from django.db.models.functions import Greatest, Least
        from django.utils import timezone
        
        now = timezone.now()
        
        # Pre-wrap division expressions to specify output_field
        variant_perc_discount = ExpressionWrapper(
            F(f"{prefix}price") * F(f"{prefix}offer_value") / 100.0,
            output_field=DecimalField()
        )
        category_perc_discount = ExpressionWrapper(
            F(f"{prefix}price") * F(f"{prefix}product__category__offer_value") / 100.0,
            output_field=DecimalField()
        )
        parent_perc_discount = ExpressionWrapper(
            F(f"{prefix}price") * F(f"{prefix}product__category__parent__offer_value") / 100.0,
            output_field=DecimalField()
        )
        # Variant discount
        variant_discount = Case(
            When(**{
                f"{prefix}offer_type": 'percentage',
                f"{prefix}offer_value__gt": 0,
                "then": variant_perc_discount
            }),
            When(**{
                f"{prefix}offer_type": 'flat',
                f"{prefix}offer_value__gt": 0,
                "then": F(f"{prefix}offer_value")
            }),
            default=Value(0.0),
            output_field=DecimalField()
        )
        # Category discount
        category_discount = Case(
            # Percentage offer:
            When(
                Q(**{f"{prefix}product__category__is_active": True}) &
                Q(**{f"{prefix}product__category__is_deleted": False}) &
                Q(**{f"{prefix}product__category__offer_type": 'percentage'}) &
                Q(**{f"{prefix}product__category__offer_value__gt": 0}) &
                (Q(**{f"{prefix}product__category__expiry_date__isnull": True}) | Q(**{f"{prefix}product__category__expiry_date__gte": now})) &
                (Q(**{f"{prefix}product__category__min_product_price__isnull": True}) | Q(**{f"{prefix}price__gte": F(f"{prefix}product__category__min_product_price")})),
                
                then=Case(
                    When(
                        Q(**{f"{prefix}product__category__max_discount__isnull": False}) & Q(**{f"{prefix}product__category__max_discount__gt": 0}),
                        then=Least(
                            category_perc_discount,
                            F(f"{prefix}product__category__max_discount"),
                            output_field=DecimalField()
                        )
                    ),
                    default=category_perc_discount
                )
            ),
            # Flat offer:
            When(
                Q(**{f"{prefix}product__category__is_active": True}) &
                Q(**{f"{prefix}product__category__is_deleted": False}) &
                Q(**{f"{prefix}product__category__offer_type": 'flat'}) &
                Q(**{f"{prefix}product__category__offer_value__gt": 0}) &
                (Q(**{f"{prefix}product__category__expiry_date__isnull": True}) | Q(**{f"{prefix}product__category__expiry_date__gte": now})) &
                (Q(**{f"{prefix}product__category__min_product_price__isnull": True}) | Q(**{f"{prefix}price__gte": F(f"{prefix}product__category__min_product_price")})),
                
                then=F(f"{prefix}product__category__offer_value")
            ),
            default=Value(0.0),
            output_field=DecimalField()
        )
        # Parent Category discount
        parent_category_discount = Case(
            # Percentage offer:
            When(
                Q(**{f"{prefix}product__category__parent__isnull": False}) &
                Q(**{f"{prefix}product__category__parent__is_active": True}) &
                Q(**{f"{prefix}product__category__parent__is_deleted": False}) &
                Q(**{f"{prefix}product__category__parent__offer_type": 'percentage'}) &
                Q(**{f"{prefix}product__category__parent__offer_value__gt": 0}) &
                (Q(**{f"{prefix}product__category__parent__expiry_date__isnull": True}) | Q(**{f"{prefix}product__category__parent__expiry_date__gte": now})) &
                (Q(**{f"{prefix}product__category__parent__min_product_price__isnull": True}) | Q(**{f"{prefix}price__gte": F(f"{prefix}product__category__parent__min_product_price")})),
                
                then=Case(
                    When(
                        Q(**{f"{prefix}product__category__parent__max_discount__isnull": False}) & Q(**{f"{prefix}product__category__parent__max_discount__gt": 0}),
                        then=Least(
                            parent_perc_discount,
                            F(f"{prefix}product__category__parent__max_discount"),
                            output_field=DecimalField()
                        )
                    ),
                    default=parent_perc_discount
                )
            ),
            # Flat offer:
            When(
                Q(**{f"{prefix}product__category__parent__isnull": False}) &
                Q(**{f"{prefix}product__category__parent__is_active": True}) &
                Q(**{f"{prefix}product__category__parent__is_deleted": False}) &
                Q(**{f"{prefix}product__category__parent__offer_type": 'flat'}) &
                Q(**{f"{prefix}product__category__parent__offer_value__gt": 0}) &
                (Q(**{f"{prefix}product__category__parent__expiry_date__isnull": True}) | Q(**{f"{prefix}product__category__parent__expiry_date__gte": now})) &
                (Q(**{f"{prefix}product__category__parent__min_product_price__isnull": True}) | Q(**{f"{prefix}price__gte": F(f"{prefix}product__category__parent__min_product_price")})),
                
                then=F(f"{prefix}product__category__parent__offer_value")
            ),
            default=Value(0.0),
            output_field=DecimalField()
        )
        # Best discount amount
        discount_amount_expr = Greatest(
            variant_discount,
            category_discount,
            parent_category_discount,
            output_field=DecimalField()
        )
        # Effective price expression, capped at 0
        return Case(
            When(
                **{
                    f"{prefix}price__lt": discount_amount_expr,
                    "then": Value(0.0)
                }
            ),
            default=F(f"{prefix}price") - discount_amount_expr,
            output_field=DecimalField()
        )
    def __str__(self):
        return f"{self.product.name} - {self.sku}"


    def __str__(self):
        return f"{self.product.name} - {self.sku}"


class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='images')
    # If null, this is a general product image. If set, it belongs to a specific variant.
    variant = models.ForeignKey(
        ProductVariant, 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True, 
        related_name='images'
    )
    image_url = models.URLField()
    is_primary = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Image for {self.product.name} (Variant: {self.variant.sku if self.variant else 'Global'})"