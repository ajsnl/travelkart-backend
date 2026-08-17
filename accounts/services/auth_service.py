from rest_framework_simplejwt.tokens import RefreshToken

class AuthService:
    @staticmethod
    def create_auth_tokens(user):
        """Generates access and refresh tokens for a user."""
        refresh = RefreshToken.for_user(user)
        return {
            "access_token": str(refresh.access_token),
            "refresh_token": str(refresh),
        }

    @staticmethod
    def set_auth_cookies(response, access_token, refresh_token):
        """Attaches access and refresh tokens to response cookies."""
        from django.conf import settings
        secure = not settings.DEBUG
        samesite = "Lax" if settings.DEBUG else "None"
        domain = settings.SESSION_COOKIE_DOMAIN if not settings.DEBUG else None

        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=True,
            secure=secure,      # True in production (HTTPS)
            samesite=samesite,
            domain=domain,
            path="/",
        )
        response.set_cookie(
            key="refresh_token",
            value=refresh_token,
            httponly=True,
            secure=secure,
            samesite=samesite,
            domain=domain,
            path="/",
        )
        return response

    @staticmethod
    def delete_auth_cookies(response):
        from django.conf import settings
        samesite = "Lax" if settings.DEBUG else "None"
        domain = settings.SESSION_COOKIE_DOMAIN if not settings.DEBUG else None
        response.delete_cookie(
            "access_token",
            domain=domain,
            path="/",
            samesite=samesite
        )
        response.delete_cookie(
            "refresh_token",
            domain=domain,
            path="/"
        )
        return response

    @staticmethod
    def refresh_tokens(refresh_token):
        """Generates new access and rotates the refresh token."""
        refresh = RefreshToken(refresh_token)
        new_access = str(refresh.access_token)
        
        # Blacklist the old refresh token
        try:
            refresh.blacklist()
        except AttributeError:
            pass

        # Rotate refresh token: generate new JTI, expiration, and issue time
        refresh.set_jti()
        refresh.set_exp()
        refresh.set_iat()
        new_refresh = str(refresh)
        
        return new_access, new_refresh

    @staticmethod
    def blacklist_token(refresh_token):
        """Blacklists the given refresh token."""
        if refresh_token:
            token = RefreshToken(refresh_token)
            token.blacklist()
