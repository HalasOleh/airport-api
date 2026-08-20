"""JWT authentication that accepts either an Authorization header or a cookie."""
from django.conf import settings
from django.middleware.csrf import CsrfViewMiddleware
from rest_framework import exceptions
from rest_framework_simplejwt.authentication import JWTAuthentication


class _CSRFCheck(CsrfViewMiddleware):
    """CsrfViewMiddleware exposed as something callable outside the chain."""

    def _reject(self, request, reason):
        return reason


class CookieJWTAuthentication(JWTAuthentication):
    """Read the token from the Authorization header, then from the cookie.

    Two credential styles with two different threat models:

    * **Header** - the caller had to attach it deliberately. A third-party page
      cannot make the browser add it, so there is nothing to forge. Used by
      mobile clients, scripts and the API docs.
    * **Cookie** - the browser attaches it to *every* request to this origin,
      including ones started by another site's HTML. That is what makes the
      WebSocket handshake work, and it is also exactly the property CSRF
      exploits, so the cookie path has to carry a CSRF check.

    DRF marks every APIView csrf_exempt, so the project-wide CsrfViewMiddleware
    never protects these endpoints. The check therefore has to live here, the
    same way SessionAuthentication does it.
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
        # Only after the token is known good: a CSRF failure on garbage is
        # noise, and enforcing before validation leaks whether a cookie exists.
        self.enforce_csrf(request)
        return self.get_user(validated_token), validated_token

    def enforce_csrf(self, request):
        """Run Django's CSRF check by hand. Safe methods pass through."""
        check = _CSRFCheck(lambda req: None)
        check.process_request(request)
        reason = check.process_view(request, None, (), {})
        if reason:
            raise exceptions.PermissionDenied(f"CSRF Failed: {reason}")
