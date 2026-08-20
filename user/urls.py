from django.urls import path
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenVerifyView,
)

from user.views import (
    CookieTokenRefreshView,
    CreateUserView,
    LoginUserView,
    LogoutView,
    ManageUserView,
)

app_name = "user"

urlpatterns = [
    path("register/", CreateUserView.as_view(), name="create"),
    path("login/", LoginUserView.as_view(), name="login"),
    path("login/refresh/", CookieTokenRefreshView.as_view(), name="token_refresh"),
    path("logout/", LogoutView.as_view(), name="logout"),
    # Kept for non-browser clients that expect the plain SimpleJWT endpoint.
    path("token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("me/", ManageUserView.as_view(), name="manage_user"),
    path("login/verify/", TokenVerifyView.as_view(), name="token_verify"),
]
