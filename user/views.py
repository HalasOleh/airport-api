from django.conf import settings
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from user.authentication import CookieJWTAuthentication
from user.jwt_cookies import clear_jwt_cookies, set_jwt_cookies
from user.serializer import UserSerializer


class CreateUserView(generics.CreateAPIView):
    serializer_class = UserSerializer
    permission_classes = ()


class LoginUserView(TokenObtainPairView):
    """Return the tokens in the body *and* set them as httpOnly cookies.

    The body keeps non-browser clients working unchanged. The cookies are what
    make the WebSocket handshake authenticate, since `new WebSocket()` cannot
    send an Authorization header.
    """

    permission_classes = ()

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        if response.status_code == status.HTTP_200_OK:
            set_jwt_cookies(
                response,
                access=response.data.get("access"),
                refresh=response.data.get("refresh"),
            )
        return response


class CookieTokenRefreshView(TokenRefreshView):
    """Refresh using the cookie when the body does not carry the token.

    The refresh cookie is httpOnly, so the page cannot read it and put it in
    the request body - the view has to look it up itself.
    """

    permission_classes = ()

    def post(self, request, *args, **kwargs):
        if "refresh" not in request.data:
            cookie_refresh = request.COOKIES.get(settings.JWT_REFRESH_COOKIE)
            if cookie_refresh:
                # request.data can be an immutable QueryDict.
                request._full_data = {**request.data, "refresh": cookie_refresh}

        response = super().post(request, *args, **kwargs)
        if response.status_code == status.HTTP_200_OK:
            # ROTATE_REFRESH_TOKENS is on, so a new refresh comes back too and
            # the old cookie has to be replaced or the next refresh fails.
            set_jwt_cookies(
                response,
                access=response.data.get("access"),
                refresh=response.data.get("refresh"),
            )
        return response


class LogoutView(APIView):
    """Clear the cookies.

    With httpOnly cookies the page cannot delete them itself, so logging out
    has to be a request the server answers with expired Set-Cookie headers.
    """

    authentication_classes = (CookieJWTAuthentication,)
    permission_classes = (AllowAny,)

    def post(self, request):
        return clear_jwt_cookies(Response(status=status.HTTP_204_NO_CONTENT))


class ManageUserView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer
    authentication_classes = (CookieJWTAuthentication,)
    permission_classes = (IsAuthenticated,)

    def get_object(self):
        return self.request.user
