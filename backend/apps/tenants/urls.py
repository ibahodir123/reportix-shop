from django.urls import path

from .auth_views import LoginView, LogoutView, MeView, csrf

urlpatterns = [
    path("csrf/", csrf, name="auth-csrf"),
    path("login/", LoginView.as_view(), name="auth-login"),
    path("logout/", LogoutView.as_view(), name="auth-logout"),
    path("me/", MeView.as_view(), name="auth-me"),
]
