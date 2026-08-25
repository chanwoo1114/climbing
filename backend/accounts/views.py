from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from rest_framework_simplejwt.views import TokenObtainPairView

from accounts.serializers import (
    LoginSerializer,
    LogoutSerializer,
    MeSerializer,
    RegisterSerializer,
)


@extend_schema(tags=["auth"])
class RegisterView(generics.CreateAPIView):
    """이메일 회원가입. 공개 엔드포인트."""

    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]
    authentication_classes = []


@extend_schema(tags=["auth"])
class LoginView(TokenObtainPairView):
    """이메일 + 비밀번호로 JWT 토큰 쌍 발급. 공개 엔드포인트."""

    serializer_class = LoginSerializer
    permission_classes = [AllowAny]
    authentication_classes = []


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


@extend_schema(tags=["users"])
class MeView(generics.RetrieveUpdateAPIView):
    """내 정보 조회/수정."""

    serializer_class = MeSerializer

    def get_object(self):
        return self.request.user
