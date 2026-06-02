from allauth.socialaccount.signals import pre_social_login
from django.dispatch import receiver
from django.contrib.auth import get_user_model

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