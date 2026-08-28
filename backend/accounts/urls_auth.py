from django.urls import path

from accounts.views import (
    KakaoAuthorizeView,
    KakaoCallbackView,
    RefreshView,
    LoginView,
    PasswordChangeView,
    LogoutView,
    PasswordResetConfirmView,
    PasswordResetRequestView,
    RegisterView,
    ResendVerificationView,
    SocialAccountListView,
    SocialAccountUnlinkView,
    VerifyEmailView,
)

app_name = "auth"

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("login/", LoginView.as_view(), name="login"),
    path("refresh/", RefreshView.as_view(), name="refresh"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("verify-email/", VerifyEmailView.as_view(), name="verify-email"),
    path(
        "verify-email/resend/",
        ResendVerificationView.as_view(),
        name="verify-email-resend",
    ),
    path(
        "password-reset/",
        PasswordResetRequestView.as_view(),
        name="password-reset",
    ),
    path(
        "password/change/",
        PasswordChangeView.as_view(),
        name="password-change",
    ),
    path(
        "password-reset/confirm/",
        PasswordResetConfirmView.as_view(),
        name="password-reset-confirm",
    ),
    # 소셜 로그인 (accounts/social)
    path("kakao/authorize/", KakaoAuthorizeView.as_view(), name="kakao-authorize"),
    path("kakao/callback/", KakaoCallbackView.as_view(), name="kakao-callback"),
    path("social/", SocialAccountListView.as_view(), name="social-list"),
    path(
        "social/<str:provider>/",
        SocialAccountUnlinkView.as_view(),
        name="social-unlink",
    ),
]
