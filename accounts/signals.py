from allauth.socialaccount.signals import pre_social_login
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from accounts.models import Referral
from accounts.services.referral_service import process_referral_reward

User = get_user_model()


@receiver(pre_social_login)
def link_google_user(request, sociallogin, **kwargs):
    email = sociallogin.account.extra_data.get("email")

    if not email:
        return

    try:
        user = User.objects.get(email=email)

        #  LINK EXISTING USER (PREVENT DUPLICATE)
        sociallogin.connect(request, user)

        if not user.is_verified:
            user.is_verified = True
            user.save()

    except User.DoesNotExist:
        user = sociallogin.user
        user.is_verified = True


@receiver(post_save, sender='orders.Order')
def update_referral_status_on_order_created(sender, instance, created, **kwargs):
    """
    On order creation, if user has a referral link in 'signed_up' state,
    progress status to 'first_order'.
    """
    if created:
        user = instance.user
        try:
            referral = Referral.objects.get(referred_user=user)
            if referral.status == 'signed_up':
                referral.status = 'first_order'
                referral.save()
        except Referral.DoesNotExist:
            pass


@receiver(post_save, sender='orders.Order')
def trigger_referral_reward_on_order_paid(sender, instance, **kwargs):
    """
    When an order's payment status is updated to 'paid', verify first-order
    eligibility and distribute referral rewards.
    """
    if instance.payment_status == 'paid':
        process_referral_reward(instance)
