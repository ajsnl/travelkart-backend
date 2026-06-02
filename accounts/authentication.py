from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.authentication import CSRFCheck
from rest_framework.exceptions import PermissionDenied


class CookieJWTAuthentication(JWTAuthentication):
    def authenticate(self, request):
        access_token = request.COOKIES.get("access_token")

        if not access_token:
            return None

        validated_token = self.get_validated_token(access_token)
        user = self.get_user(validated_token)

        # Enforce CSRF check for cookie-based authentication
        self.enforce_csrf(request)

        return (user, validated_token)

    def enforce_csrf(self, request):
        def dummy_get_response(request):
            return None

        check = CSRFCheck(dummy_get_response)
        check.process_request(request)
        reason = check.process_view(request, None, (), {})
        if reason:
            raise PermissionDenied(f"CSRF Failed: {reason}")


class CookieJWTAuthenticationWithoutCSRF(CookieJWTAuthentication):
    def enforce_csrf(self, request):
        return  # Bypass CSRF check for logout actions
