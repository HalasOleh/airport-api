"""Cookie-based JWT: the login sets it, the API reads it, CSRF guards it."""
import pytest
from django.conf import settings
from django.urls import reverse


@pytest.mark.django_db
def test_login_sets_httponly_cookies(api_client, user):
    response = api_client.post(
        reverse("user:login"),
        {"email": user.email, "password": "buyer-pass-123"},
        format="json",
    )

    assert response.status_code == 200
    access = response.cookies[settings.JWT_ACCESS_COOKIE]
    assert access["httponly"] is True
    # Path "/" is what makes one cookie cover both /api/... and /ws/...
    assert access["path"] == "/"
    assert access["samesite"] == "Lax"
    assert settings.JWT_REFRESH_COOKIE in response.cookies


@pytest.mark.django_db
def test_cookie_alone_authenticates_a_get(api_client, user):
    api_client.post(
        reverse("user:login"),
        {"email": user.email, "password": "buyer-pass-123"},
        format="json",
    )
    # No Authorization header is ever set on this client.
    response = api_client.get(reverse("user:manage_user"))

    assert response.status_code == 200
    assert response.data["email"] == user.email


@pytest.mark.django_db
def test_no_credentials_is_rejected(api_client):
    assert api_client.get(reverse("user:manage_user")).status_code == 401


@pytest.mark.django_db
def test_header_still_works_for_non_browser_clients(api_client, user):
    tokens = api_client.post(
        reverse("user:login"),
        {"email": user.email, "password": "buyer-pass-123"},
        format="json",
    ).data
    api_client.cookies.clear()
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

    assert api_client.get(reverse("user:manage_user")).status_code == 200


@pytest.mark.django_db
def test_logout_clears_the_cookies(api_client, user):
    api_client.post(
        reverse("user:login"),
        {"email": user.email, "password": "buyer-pass-123"},
        format="json",
    )
    response = api_client.post(reverse("user:logout"))

    assert response.status_code == 204
    # Deleting a cookie means sending it back empty and already expired.
    assert response.cookies[settings.JWT_ACCESS_COOKIE].value == ""


@pytest.mark.django_db
def test_refresh_reads_the_cookie_when_the_body_is_empty(api_client, user):
    api_client.post(
        reverse("user:login"),
        {"email": user.email, "password": "buyer-pass-123"},
        format="json",
    )
    # The refresh cookie is httpOnly, so a page can never put it in the body.
    response = api_client.post(reverse("user:token_refresh"), {}, format="json")

    assert response.status_code == 200
    assert settings.JWT_ACCESS_COOKIE in response.cookies


@pytest.mark.django_db
def test_unsafe_request_on_a_cookie_needs_csrf(user, flight, airplane):
    """A cookie rides along with cross-site requests, so the server needs
    proof the request came from our own page. DRF marks every APIView
    csrf_exempt, so this check lives in CookieJWTAuthentication."""
    from rest_framework.test import APIClient

    client = APIClient(enforce_csrf_checks=True)
    client.post(
        reverse("user:login"),
        {"email": user.email, "password": "buyer-pass-123"},
        format="json",
    )

    response = client.post(reverse("ai_bot:chat-dialog-list"), {"title": "x"}, format="json")

    assert response.status_code == 403
    assert "CSRF" in str(response.data)
