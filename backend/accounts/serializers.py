from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import RegexValidator
from rest_framework import serializers
from rest_framework.validators import UniqueValidator
from rest_framework_simplejwt.serializers import (
    TokenObtainPairSerializer,
    TokenRefreshSerializer,
)
from rest_framework_simplejwt.settings import api_settings as jwt_settings

from accounts.exceptions import EmailNotVerified, UserInactive
from accounts.models import SocialAccount, User
from crews.models import Crew
from crews.serializers import MainCrewField
from crews.services import is_active_member
from gyms.models import Gym

# 입력 규칙 — 프론트(front/src/lib/validation.ts)와 동일하게 유지할 것.
# 클라이언트 검증은 UX용일 뿐이라 서버에서도 같은 규칙을 강제한다.
NICKNAME_MIN_LENGTH = 2
NICKNAME_MAX_LENGTH = 30
NICKNAME_FORMAT_VALIDATOR = RegexValidator(
    regex=r"^[가-힣a-zA-Z0-9_-]+$",
    message="닉네임은 한글, 영문, 숫자, _ - 만 사용할 수 있습니다.",
)

# accounts_user.email 컬럼(varchar 254)과 맞춘다. 시리얼라이저에서 막지 않으면
# DB까지 내려가 DataError(500)가 난다 — 검증 실패는 400으로 돌려줘야 한다.
EMAIL_MAX_LENGTH = 254

# 비밀번호 길이 상한 — 한국 관행(8~16자). accounts/validators.py 가 규칙의 원본이고
# 여기서는 시리얼라이저 필드 상한으로 재사용한다 (초장문 해시 CPU 소모 방지 겸).
from accounts.validators import PASSWORD_MAX_LENGTH  # noqa: E402


class UserSerializer(serializers.ModelSerializer):
    """공개 프로필 필드."""

    class Meta:
        model = User
        fields = ("id", "email", "nickname", "created_at")
        read_only_fields = fields


class RegisterSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(
        max_length=EMAIL_MAX_LENGTH,
        validators=[
            UniqueValidator(
                # all_objects: DB의 UNIQUE 제약은 soft delete 를 구분하지 않는다.
                # objects 로 검사하면 탈퇴 계정의 이메일이 통과해 500이 난다.
                queryset=User.all_objects.all(),
                message="이미 가입된 이메일입니다.",
                # 대소문자만 다른 이메일도 중복으로 본다 (저장은 소문자로 통일).
                lookup="iexact",
            )
        ],
        error_messages={
            "invalid": "이메일 형식이 올바르지 않습니다.",
            "blank": "이메일을 입력해 주세요.",
            "max_length": f"이메일은 {EMAIL_MAX_LENGTH}자 이하여야 합니다.",
        },
    )
    nickname = serializers.CharField(
        min_length=NICKNAME_MIN_LENGTH,
        max_length=NICKNAME_MAX_LENGTH,
        trim_whitespace=True,
        validators=[
            NICKNAME_FORMAT_VALIDATOR,
            UniqueValidator(
                queryset=User.all_objects.all(),
                message="이미 사용 중인 닉네임입니다.",
                # 표시 이름이라 대소문자는 보존하되, 대소문자만 다른 중복은 막는다.
                lookup="iexact",
            ),
        ],
        error_messages={
            "blank": "닉네임을 입력해 주세요.",
            "min_length": f"닉네임은 {NICKNAME_MIN_LENGTH}자 이상이어야 합니다.",
            "max_length": f"닉네임은 {NICKNAME_MAX_LENGTH}자 이하여야 합니다.",
        },
    )
    password = serializers.CharField(
        write_only=True,
        max_length=PASSWORD_MAX_LENGTH,
        style={"input_type": "password"},
        error_messages={
            "blank": "비밀번호를 입력해 주세요.",
            "max_length": f"비밀번호는 {PASSWORD_MAX_LENGTH}자 이하여야 합니다.",
        },
    )

    class Meta:
        model = User
        fields = ("id", "email", "nickname", "password")
        read_only_fields = ("id",)

    def validate_email(self, value):
        # 저장·조회 모두 소문자로 통일한다 (UserManager.normalize_email 과 동일).
        return User.objects.normalize_email(value)

    def validate(self, attrs):
        """비밀번호 검증에 이메일·닉네임을 함께 넘긴다.

        validate_password(password) 처럼 user 없이 호출하면
        UserAttributeSimilarityValidator 가 통째로 건너뛰어져서,
        비밀번호를 이메일과 똑같이 써도 통과한다.
        """
        candidate = User(
            email=attrs.get("email", ""), nickname=attrs.get("nickname", "")
        )
        try:
            validate_password(attrs.get("password", ""), user=candidate)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"password": list(exc.messages)})
        return attrs

    def create(self, validated_data):
        from accounts.services import register_user

        return register_user(**validated_data)


class MeSerializer(serializers.ModelSerializer):
    # 프로필 수정에서도 가입과 같은 닉네임 규칙을 적용한다.
    nickname = serializers.CharField(
        min_length=NICKNAME_MIN_LENGTH,
        max_length=NICKNAME_MAX_LENGTH,
        trim_whitespace=True,
        required=False,
        validators=[
            NICKNAME_FORMAT_VALIDATOR,
            UniqueValidator(
                queryset=User.all_objects.all(),
                message="이미 사용 중인 닉네임입니다.",
                # 표시 이름이라 대소문자는 보존하되, 대소문자만 다른 중복은 막는다.
                lookup="iexact",
            ),
        ],
        error_messages={
            "blank": "닉네임을 입력해 주세요.",
            "min_length": f"닉네임은 {NICKNAME_MIN_LENGTH}자 이상이어야 합니다.",
            "max_length": f"닉네임은 {NICKNAME_MAX_LENGTH}자 이하여야 합니다.",
        },
    )
    bio = serializers.CharField(source="profile.bio", allow_blank=True, required=False)
    image = serializers.URLField(
        source="profile.image", allow_blank=True, required=False
    )
    # 홈짐은 pk 로 쓰고, 화면 표시용 이름은 읽기 전용으로 함께 내려준다.
    home_gym = serializers.PrimaryKeyRelatedField(
        source="profile.home_gym",
        queryset=Gym.objects.all(),
        allow_null=True,
        required=False,
        error_messages={"does_not_exist": "존재하지 않는 암장입니다."},
    )
    home_gym_name = serializers.CharField(
        source="profile.home_gym.name", read_only=True, default=None
    )
    # 대표 크루 — 쓰기는 pk(내가 활동 중인 크루만), 읽기는 {id, name}.
    main_crew = MainCrewField(
        source="profile.main_crew",
        queryset=Crew.objects.all(),
        allow_null=True,
        required=False,
        error_messages={"does_not_exist": "존재하지 않는 크루입니다."},
    )

    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "nickname",
            "bio",
            "image",
            "home_gym",
            "home_gym_name",
            "main_crew",
            "email_verified_at",
            "created_at",
        )
        read_only_fields = (
            "id",
            "email",
            "home_gym_name",
            "email_verified_at",
            "created_at",
        )

    def validate_main_crew(self, crew):
        if crew is not None and not is_active_member(crew, self.instance):
            raise serializers.ValidationError(
                "가입한 크루만 대표 크루로 설정할 수 있습니다."
            )
        return crew

    def update(self, instance, validated_data):
        profile_data = validated_data.pop("profile", {})
        instance = super().update(instance, validated_data)
        if profile_data:
            for field, value in profile_data.items():
                setattr(instance.profile, field, value)
            instance.profile.save(update_fields=[*profile_data, "updated_at"])
        return instance


class PublicProfileSerializer(serializers.ModelSerializer):
    """다른 회원이 보는 프로필 (GET users/{id}/). 이메일은 내려주지 않는다.

    follower_count / following_count / is_following 은 뷰가
    social.services.annotate_follow_stats 로 붙인 어노테이션을 그대로 읽는다.
    """

    bio = serializers.SerializerMethodField()
    image = serializers.SerializerMethodField()
    home_gym = serializers.SerializerMethodField()
    main_crew = serializers.SerializerMethodField()
    follower_count = serializers.IntegerField(read_only=True)
    following_count = serializers.IntegerField(read_only=True)
    is_following = serializers.BooleanField(read_only=True)
    is_me = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id",
            "nickname",
            "bio",
            "image",
            "home_gym",
            "main_crew",
            "follower_count",
            "following_count",
            "is_following",
            "is_me",
            "created_at",
        )
        read_only_fields = fields

    def _profile(self, obj):
        # createsuperuser·admin 으로 만든 계정은 프로필이 없을 수 있다.
        return getattr(obj, "profile", None)

    def get_bio(self, obj) -> str:
        profile = self._profile(obj)
        return profile.bio if profile else ""

    def get_image(self, obj) -> str | None:
        profile = self._profile(obj)
        return (profile.image or None) if profile else None

    def get_home_gym(self, obj) -> dict | None:
        profile = self._profile(obj)
        gym = profile.home_gym if profile else None
        return {"id": gym.id, "name": gym.name} if gym else None

    def get_main_crew(self, obj) -> dict | None:
        profile = self._profile(obj)
        crew = profile.main_crew if profile else None
        return {"id": crew.id, "name": crew.name} if crew else None

    def get_is_me(self, obj) -> bool:
        request = self.context.get("request")
        return bool(request and request.user.pk == obj.pk)


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField()


class EmailSerializer(serializers.Serializer):
    """인증 메일 재전송 / 비밀번호 재설정 요청 입력."""

    email = serializers.EmailField(
        max_length=EMAIL_MAX_LENGTH,
        error_messages={
            "invalid": "이메일 형식이 올바르지 않습니다.",
            "blank": "이메일을 입력해 주세요.",
        },
    )


class VerifyEmailSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=512)


class PasswordResetConfirmSerializer(serializers.Serializer):
    """새 비밀번호 규칙 검증은 user 가 필요해서 services.confirm_password_reset 에서 한다."""

    uid = serializers.CharField(max_length=64)
    token = serializers.CharField(max_length=128)
    password = serializers.CharField(
        write_only=True,
        max_length=PASSWORD_MAX_LENGTH,
        style={"input_type": "password"},
        error_messages={
            "blank": "비밀번호를 입력해 주세요.",
            "max_length": f"비밀번호는 {PASSWORD_MAX_LENGTH}자 이하여야 합니다.",
        },
    )


class LoginSerializer(TokenObtainPairSerializer):
    """로그인 실패 메시지를 한국어로 통일.

    어느 쪽이 틀렸는지(이메일/비밀번호)는 알려주지 않는다 — 계정 존재 여부가
    새어나가지 않도록.
    """

    default_error_messages = {
        "no_active_account": "이메일 또는 비밀번호가 올바르지 않습니다."
    }

    @classmethod
    def get_token(cls, user):
        # 비밀번호 검증을 통과한 뒤에만 여기 온다 — 미인증 여부는 계정 존재를
        # 이미 아는 본인에게만 알려지므로 계정 열거로 이어지지 않는다.
        # (validate() 안의 update_last_login 보다 먼저라 last_login 도 안 바뀐다.)
        if user.email_verified_at is None:
            raise EmailNotVerified()
        return super().get_token(user)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 로그인 입력에도 상한을 둔다. 없으면 초장문 문자열이 그대로
        # 해시 함수까지 내려가 CPU를 소모한다.
        # (max_length 속성만 바꾸면 validator가 붙지 않으므로 필드를 교체한다.)
        self.fields[self.username_field] = serializers.CharField(
            max_length=EMAIL_MAX_LENGTH, write_only=True
        )
        self.fields["password"] = serializers.CharField(
            max_length=PASSWORD_MAX_LENGTH,
            write_only=True,
            style={"input_type": "password"},
        )


class RefreshSerializer(TokenRefreshSerializer):
    """refresh 시 토큰 주인이 아직 유효한지 확인한다.

    simplejwt 기본 구현은 서명·만료만 보고 새 access 를 내준다. 그러면 탈퇴(soft
    delete)하거나 비활성화된 계정도 refresh 만료(14일)까지 access 를 계속 받는다.
    User.objects 는 is_deleted=False 만 반환하므로 탈퇴 계정은 여기서 걸린다.
    """

    def validate(self, attrs):
        # super() 는 ROTATE+BLACKLIST 로 이 토큰을 블랙리스트에 올리므로, 파싱과
        # 유저 확인은 그 전에 한다. 서명·만료 오류는 TokenError → 뷰가 401 로 바꾼다.
        user_id = self.token_class(attrs["refresh"]).get(jwt_settings.USER_ID_CLAIM)
        if not User.objects.filter(pk=user_id, is_active=True).exists():
            raise UserInactive()
        return super().validate(attrs)


# ---- 소셜 로그인 (accounts/social) ------------------------------------------


class KakaoAuthorizeSerializer(serializers.Serializer):
    """GET auth/kakao/authorize/ 응답 (스키마 문서용)."""

    authorize_url = serializers.URLField(read_only=True)
    state = serializers.CharField(read_only=True)


class KakaoCallbackSerializer(serializers.Serializer):
    """카카오가 redirect_uri 로 돌려준 ?code=&state= 를 그대로 넘긴다."""

    code = serializers.CharField(
        max_length=512, error_messages={"blank": "인가 코드가 없습니다."}
    )
    state = serializers.CharField(
        max_length=512, error_messages={"blank": "state 가 없습니다."}
    )


class SocialTokenSerializer(serializers.Serializer):
    """소셜 로그인 성공 응답. LoginView 의 토큰 쌍 + 신규 가입 여부."""

    access = serializers.CharField(read_only=True)
    refresh = serializers.CharField(read_only=True)
    is_new = serializers.BooleanField(read_only=True)


class SocialAccountSerializer(serializers.ModelSerializer):
    """내가 연결한 소셜 계정 목록 항목. provider 토큰·uid 는 내려주지 않는다."""

    class Meta:
        model = SocialAccount
        fields = ("provider", "connected_at", "email_at_provider")
        read_only_fields = fields


class PasswordChangeSerializer(serializers.Serializer):
    """로그인 상태 비밀번호 변경 입력. 새 비밀번호 규칙 검증은 user 가 필요해서
    services.change_password 에서 한다."""

    current_password = serializers.CharField(
        write_only=True,
        max_length=PASSWORD_MAX_LENGTH,
        style={"input_type": "password"},
        error_messages={"blank": "현재 비밀번호를 입력해 주세요."},
    )
    new_password = serializers.CharField(
        write_only=True,
        max_length=PASSWORD_MAX_LENGTH,
        style={"input_type": "password"},
        error_messages={
            "blank": "새 비밀번호를 입력해 주세요.",
            "max_length": f"비밀번호는 {PASSWORD_MAX_LENGTH}자 이하여야 합니다.",
        },
    )


class TokenPairSerializer(serializers.Serializer):
    """비밀번호 변경 후 새로 발급하는 토큰 쌍 (응답 스키마용)."""

    access = serializers.CharField(read_only=True)
    refresh = serializers.CharField(read_only=True)


class WithdrawSerializer(serializers.Serializer):
    """회원 탈퇴 입력. 비밀번호가 있는 계정은 필수, 소셜 전용 계정은 생략 가능."""

    password = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True,
        default="",
        max_length=PASSWORD_MAX_LENGTH,
        style={"input_type": "password"},
    )
