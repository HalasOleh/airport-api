from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView
from django.contrib import admin
from django.urls import path, include
from tickets.views import StripeWebhookView

urlpatterns = [
    path('admin/', admin.site.urls),
    path("", include("airports.urls", namespace="airports")),

    path("api/payments/webhook/", StripeWebhookView.as_view(), name="payments-webhook"),
    path("tickets/", include("tickets.urls", namespace="tickets")),
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),

    path('api/schema/swagger-ui/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/schema/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
    path('api/user/', include('user.urls', namespace="user")),
    path('', include('ai_bot.urls', namespace="ai_bot")),
]
