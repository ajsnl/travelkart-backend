from django.db import transaction
from django.utils import timezone
from decimal import Decimal
from datetime import timedelta
from accounts.models import Referral
from wallet.models import Wallet, WalletTransaction
from django.contrib.auth import get_user_model

User = get_user_model()

def process_referral_reward(order):
    """
    Validates first order eligibility (paid, >= ₹100, verified users, no self-referrals)
    and atomically credits rewards to the referee and referrer.
    """
    user = order.user
    
    #  Check if the user was referred
    try:
        referral = Referral.objects.get(referred_user=user)
    except Referral.DoesNotExist:
        return

    if referral.status == 'rewarded':
        return

    earlier_paid_orders = user.orders.filter(
        payment_status='paid',
        created_at__lt=order.created_at
    ).exclude(id=order.id)
    
    if earlier_paid_orders.exists():
        return

    if order.total_price < Decimal('100.00'):
        return

    referrer = referral.referrer
    if not referrer.is_verified or not user.is_verified:
        return

    #  Anti-Abuse Checks 
    if referrer.email.lower() == user.email.lower():
        return
    if referrer.phone and user.phone and referrer.phone == user.phone:
        return

    # Process reward updates atomically
    with transaction.atomic():
        # Re-fetch with select_for_update to handle concurrency
        referral = Referral.objects.select_for_update().get(id=referral.id)
        if referral.status == 'rewarded':
            return

        # Update Referral status
        referral.status = 'rewarded'
        referral.rewarded_at = timezone.now()
        referral.save()

        # Mark user as referral rewarded
        user.is_referral_rewarded = True
        user.save(update_fields=['is_referral_rewarded'])

        referred_wallet, _ = Wallet.objects.select_for_update().get_or_create(user=user)
        referred_wallet.balance += Decimal('50.00')
        referred_wallet.save()
        WalletTransaction.objects.create(
            user=user,
            amount=Decimal('50.00'),
            transaction_type='CREDIT',
            reason="Referral Reward - Signup bonus",
            status='success'
        )

        referrer_wallet, _ = Wallet.objects.select_for_update().get_or_create(user=referrer)
        referrer_wallet.balance += Decimal('99.00')
        referrer_wallet.save()
        WalletTransaction.objects.create(
            user=referrer,
            amount=Decimal('99.00'),
            transaction_type='CREDIT',
            reason=f"Referral Reward - Invited {user.email}",
            status='success'
        )

        # Referrer gets: +3 days Gold Membership ONLY IF not already gold
        if not referrer.is_gold_member:
            referrer.is_gold_member = True
            referrer.gold_purchased_at = timezone.now()
            base_time = referrer.gold_expires_at if (referrer.gold_expires_at and referrer.gold_expires_at > timezone.now()) else timezone.now()
            referrer.gold_expires_at = base_time + timedelta(days=3)
            referrer.save(update_fields=['is_gold_member', 'gold_purchased_at', 'gold_expires_at'])
