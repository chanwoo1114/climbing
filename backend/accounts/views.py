from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from accounts import services
from accounts.serializers import (
    EmailSerializer,
    LoginSerializer,
    LogoutSerializer,
    MeSerializer,
    PasswordResetConfirmSerializer,
    RefreshSerializer,
    RegisterSerializer,
    UserSerializer,
    VerifyEmailSerializer,
)
from accounts.throttles import (
    EmailSendRateThrottle,
    LoginRateThrottle,
    RegisterRateThrottle,
    ThrottledMessageMixin,
    TokenConfirmRateThrottle,
)


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


@extend_schema(tags=["auth"], request=LogoutSerializer, responses={204: None})
@extend_schema(tags=["auth"])
class RefreshView(TokenRefreshView):
    """access 재발급. 탈퇴·비활성 계정의 refresh 는 401."""

    serializer_class = RefreshSerializer


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
