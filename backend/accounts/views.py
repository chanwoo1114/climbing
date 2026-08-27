from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics, status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from accounts import services
from accounts.social import kakao
from accounts.social import services as kakao_services
from accounts.models import SocialAccount, User
from accounts.serializers import (
    EmailSerializer,
    KakaoAuthorizeSerializer,
    KakaoCallbackSerializer,
    LoginSerializer,
    LogoutSerializer,
    MeSerializer,
    PasswordResetConfirmSerializer,
    PublicProfileSerializer,
    RefreshSerializer,
    RegisterSerializer,
    SocialAccountSerializer,
    SocialTokenSerializer,
    UserSerializer,
    VerifyEmailSerializer,
)
from accounts.throttles import (
    EmailSendRateThrottle,
    LoginRateThrottle,
    RegisterRateThrottle,
    SocialLoginRateThrottle,
    ThrottledMessageMixin,
    TokenConfirmRateThrottle,
)
from common.pagination import DefaultCursorPagination
from social import services as social_services
from social.serializers import UserSummarySerializer


@extend_schema(tags=["auth"])
class RegisterView(ThrottledMessageMixin, generics.CreateAPIView):
    """이메일 회원가입. 공개 엔드포인트. 가입 직후 인증 메일이 발송된다."""

    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [RegisterRateThrottle]


@extend_schema(tags=["auth"])
class LoginView(ThrottledMessageMixin, TokenObtainPairView):
    """이메일 + 비밀번호로 JWT 토큰 쌍 발급. 공개 엔드포인트.

    이메일 미인증 계정은 403 email_not_verified 로 거부된다.
    """

    serializer_class = LoginSerializer
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [LoginRateThrottle]


@extend_schema(tags=["auth"])
class RefreshView(TokenRefreshView):
    """access 재발급. 탈퇴·비활성 계정의 refresh 는 401."""

    serializer_class = RefreshSerializer


@extend_schema(tags=["auth"], request=LogoutSerializer, responses={204: None})
class LogoutView(APIView):
    """refresh 토큰을 블랙리스트에 올려 로그아웃 처리한다."""

    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            RefreshToken(serializer.validated_data["refresh"]).blacklist()
        except TokenError:
            return Response(
                {"detail": "유효하지 않은 refresh 토큰입니다."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)


class _PublicView(ThrottledMessageMixin, APIView):
    permission_classes = [AllowAny]
    authentication_classes = []


@extend_schema(tags=["auth"], request=VerifyEmailSerializer, responses=UserSerializer)
class VerifyEmailView(_PublicView):
    """인증 메일의 토큰으로 이메일 인증을 완료한다."""

    throttle_classes = [TokenConfirmRateThrottle]

    def post(self, request):
        serializer = VerifyEmailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = services.verify_email(**serializer.validated_data)
        return Response(UserSerializer(user).data)


@extend_schema(tags=["auth"], request=EmailSerializer, responses={202: None})
class ResendVerificationView(_PublicView):
    """인증 메일 재전송. 계정 유무와 무관하게 항상 202."""

    throttle_classes = [EmailSendRateThrottle]

    def post(self, request):
        serializer = EmailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.resend_verification_email(**serializer.validated_data)
        return Response(status=status.HTTP_202_ACCEPTED)


@extend_schema(tags=["auth"], request=EmailSerializer, responses={202: None})
class PasswordResetRequestView(_PublicView):
    """비밀번호 재설정 메일 발송. 계정 유무와 무관하게 항상 202."""

    throttle_classes = [EmailSendRateThrottle]

    def post(self, request):
        serializer = EmailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.request_password_reset(**serializer.validated_data)
        return Response(status=status.HTTP_202_ACCEPTED)


@extend_schema(
    tags=["auth"], request=PasswordResetConfirmSerializer, responses={204: None}
)
class PasswordResetConfirmView(_PublicView):
    """재설정 링크의 uid/token 으로 새 비밀번호를 설정한다."""

    throttle_classes = [TokenConfirmRateThrottle]

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.confirm_password_reset(**serializer.validated_data)
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(tags=["users"])
class MeView(generics.RetrieveUpdateAPIView):
    """내 정보 조회/수정."""

    serializer_class = MeSerializer

    def get_object(self):
        # 프로필은 가입(register_user) 때 만들어지지만 createsuperuser·admin 으로
        # 만든 계정에는 없다. 없으면 여기서 만들어 profile 접근 500 을 막는다.
        services.ensure_profile(self.request.user)
        return self.request.user


@extend_schema(tags=["users"])
class UserDetailView(generics.RetrieveAPIView):
    """공개 프로필. 탈퇴(soft delete) 회원은 404.

    TODO(M2/M3): users/{id}/logs 는 climbs 앱의 ClimbLog 가 준비되면 추가.
    """

    serializer_class = PublicProfileSerializer

    def get_queryset(self):
        queryset = User.objects.select_related("profile", "profile__home_gym")
        return social_services.annotate_follow_stats(queryset, self.request.user)


class UserSearchPagination(DefaultCursorPagination):
    max_page_size = 20


@extend_schema(
    tags=["users"],
    parameters=[OpenApiParameter("q", str, description="닉네임 부분 일치 (1자 이상)")],
)
class UserSearchView(generics.ListAPIView):
    """닉네임 검색 (icontains). 커서 페이지네이션, 최대 20건."""

    serializer_class = UserSummarySerializer
    pagination_class = UserSearchPagination

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):  # drf-spectacular 스키마 생성
            return User.objects.none()
        query = self.request.query_params.get("q", "").strip()
        if not query:
            raise ValidationError({"q": "검색어를 1자 이상 입력해 주세요."})
        return (
            User.objects.filter(nickname__icontains=query)
            .select_related("profile")
            .order_by("-created_at", "-id")
        )

    def list(self, request, *args, **kwargs):
        page = self.paginate_queryset(self.get_queryset())
        context = {
            **self.get_serializer_context(),
            "following_ids": social_services.following_ids(
                request.user, [user.pk for user in page]
            ),
        }
        serializer = UserSummarySerializer(page, many=True, context=context)
        return self.get_paginated_response(serializer.data)


# ---- 소셜 로그인 (카카오) -----------------------------------------------------
#
# 프론트 계약 (/auth/kakao/callback 라우트):
#   1. GET  auth/kakao/authorize/          → {authorize_url, state}
#      state 를 sessionStorage 에 저장하고 window.location 을 authorize_url 로 보낸다.
#   2. 카카오가 KAKAO_REDIRECT_URI(프론트 라우트)로 ?code=...&state=... 리다이렉트.
#      (사용자가 취소하면 ?error=access_denied&state=... — 로그인 화면으로 되돌린다)
#   3. POST auth/kakao/callback/ {code, state} → 200/201 {access, refresh, is_new}
#      기존 로그인과 동일하게 토큰을 저장하면 끝. is_new 면 닉네임 설정 화면 등으로 안내.
#      오류: 400 invalid_state(다시 1부터) · 409 email_conflict(비밀번호 로그인 안내)
#            · 401 user_inactive · 502 kakao_error · 503 kakao_not_configured · 429


@extend_schema(tags=["auth"], responses=KakaoAuthorizeSerializer)
class KakaoAuthorizeView(_PublicView):
    """카카오 인가 페이지 URL 발급. 서명된 state 가 포함돼 세션 없이 검증한다."""

    def get(self, request):
        authorize_url, state = kakao.build_authorize_url()
        return Response({"authorize_url": authorize_url, "state": state})


@extend_schema(
    tags=["auth"],
    request=KakaoCallbackSerializer,
    responses={200: SocialTokenSerializer, 201: SocialTokenSerializer},
)
class KakaoCallbackView(_PublicView):
    """인가 코드를 서버에서 카카오 토큰으로 교환해 우리 JWT 를 발급한다.

    카카오 토큰은 프로필 조회에만 쓰고 저장하지 않는다. 신규 가입이면 201.
    """

    throttle_classes = [SocialLoginRateThrottle]

    def post(self, request):
        serializer = KakaoCallbackSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        kakao.check_state(serializer.validated_data["state"])
        user, is_new = kakao_services.login_with_kakao_code(
            serializer.validated_data["code"]
        )
        data = {**kakao_services.issue_tokens(user), "is_new": is_new}
        return Response(
            data, status=status.HTTP_201_CREATED if is_new else status.HTTP_200_OK
        )


@extend_schema(tags=["auth"], responses=SocialAccountSerializer(many=True))
class SocialAccountListView(generics.ListAPIView):
    """내가 연결한 소셜 계정 목록 (페이지네이션 없음 — provider 당 1개)."""

    serializer_class = SocialAccountSerializer
    pagination_class = None

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return SocialAccount.objects.none()
        return kakao_services.linked_accounts(self.request.user)


@extend_schema(tags=["auth"], responses={204: None})
class SocialAccountUnlinkView(APIView):
    """소셜 계정 연결 해제. 비밀번호 없는 계정의 마지막 연결이면 400 last_login_method.

    비밀번호는 auth/password-reset/ 로 먼저 만들 수 있다 (실제 이메일 계정만).
    """

    def delete(self, request, provider):
        if provider not in SocialAccount.Provider.values:
            raise NotFound("지원하지 않는 소셜 제공자입니다.")
        if kakao_services.unlink(request.user, provider) is None:
            raise NotFound("연결된 소셜 계정이 없습니다.")
        return Response(status=status.HTTP_204_NO_CONTENT)
