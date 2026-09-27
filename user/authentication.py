"""JWT authentication that accepts either an Authorization header or a cookie."""
from django.conf import settings
from django.middleware.csrf import CsrfViewMiddleware
from rest_framework import exceptions
from rest_framework_simplejwt.authentication import JWTAuthentication


class _CSRFCheck(CsrfViewMiddleware):

    def _reject(self, request, reason):
        return reason


class CookieJWTAuthentication(JWTAuthentication):
    """Read the token from the Authorization header, then from the cookie.
        A third-party page cannot make the browser add it
    DRF marks every APIView csrf_exempt, so the project-wide CsrfViewMiddleware
    never protects these endpoints
    """

    def authenticate(self, request):
        header = self.get_header(request)
        if header is not None:
            raw_token = self.get_raw_token(header)
            if raw_token is None:
                return None
            validated_token = self.get_validated_token(raw_token)
            return self.get_user(validated_token), validated_token

        raw_token = request.COOKIES.get(settings.JWT_ACCESS_COOKIE)
        if not raw_token:
            return None

        validated_token = self.get_validated_token(raw_token)
        # Only after the token is known good: enforcing before validation
        # would leak whether a cookie exists at all.
        self.enforce_csrf(request)
        return self.get_user(validated_token), validated_token

    def enforce_csrf(self, request):
        """Run Django's CSRF check by hand. Safe methods pass through."""
        check = _CSRFCheck(lambda req: None)
        check.process_request(request)
        reason = check.process_view(request, None, (), {})
        if reason:
            raise exceptions.PermissionDenied(f"CSRF Failed: {reason}")
