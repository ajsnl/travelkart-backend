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
        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=True,
            secure=False,      # True in production (HTTPS)
            samesite="Lax",
            path="/",
        )
        response.set_cookie(
            key="refresh_token",
            value=refresh_token,
            httponly=True,
            secure=False,
            samesite="Lax",
            path="/",
        )
        return response

    @staticmethod
    def delete_auth_cookies(response):
        response.delete_cookie(
            "access_token",
            path="/",
            samesite="Lax",
        )
        response.delete_cookie(
            "refresh_token",
            path="/",
            samesite="Lax",
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
