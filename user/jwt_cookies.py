"""One place that knows how JWT cookies are written and cleared.

Login, refresh and logout all need identical cookie attributes. If any of them
drifts - a different SameSite, a different Path - the browser treats it as a
different cookie and the symptom is an intermittent "logged out" that is very
hard to trace. Hence a single helper rather than three copies of set_cookie().
"""
from django.conf import settings


def _max_age(lifetime_key: str) -> int:
    """Cookie lifetime in seconds, taken from the token's own lifetime.

    Keeping these in step means the cookie disappears at roughly the moment the
    token inside it stops being accepted, instead of lingering as a dead cookie
    that produces confusing 401s.
    """
    return int(settings.SIMPLE_JWT[lifetime_key].total_seconds())


def set_jwt_cookies(response, access: str | None = None, refresh: str | None = None):
    """Attach the tokens the caller supplied; skip the ones it did not."""
    if access:
        response.set_cookie(
            settings.JWT_ACCESS_COOKIE,
            access,
            max_age=_max_age("ACCESS_TOKEN_LIFETIME"),
            httponly=True,
            secure=settings.JWT_COOKIE_SECURE,
            samesite=settings.JWT_COOKIE_SAMESITE,
            path=settings.JWT_COOKIE_PATH,
        )

    if refresh:
        response.set_cookie(
            settings.JWT_REFRESH_COOKIE,
            refresh,
            max_age=_max_age("REFRESH_TOKEN_LIFETIME"),
            httponly=True,
            secure=settings.JWT_COOKIE_SECURE,
            samesite=settings.JWT_COOKIE_SAMESITE,
            path=settings.JWT_COOKIE_PATH,
        )

    return response


def clear_jwt_cookies(response):
    """Delete both cookies.

    The path must match the one they were written with, otherwise the browser
    deletes nothing and keeps sending the old cookie.
    """
    for name in (settings.JWT_ACCESS_COOKIE, settings.JWT_REFRESH_COOKIE):
        response.delete_cookie(
            name,
            path=settings.JWT_COOKIE_PATH,
            samesite=settings.JWT_COOKIE_SAMESITE,
        )
    return response
