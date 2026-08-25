from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import RegexValidator
from rest_framework import serializers
from rest_framework.validators import UniqueValidator
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from accounts.models import User

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

    class Meta:
        model = User
        fields = ("id", "email", "nickname", "bio", "image", "created_at")
        read_only_fields = ("id", "email", "created_at")

    def update(self, instance, validated_data):
        profile_data = validated_data.pop("profile", {})
        instance = super().update(instance, validated_data)
        if profile_data:
            for field, value in profile_data.items():
                setattr(instance.profile, field, value)
            instance.profile.save(update_fields=[*profile_data, "updated_at"])
        return instance


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField()


class LoginSerializer(TokenObtainPairSerializer):
    """로그인 실패 메시지를 한국어로 통일.

    어느 쪽이 틀렸는지(이메일/비밀번호)는 알려주지 않는다 — 계정 존재 여부가
    새어나가지 않도록.
    """

    default_error_messages = {
        "no_active_account": "이메일 또는 비밀번호가 올바르지 않습니다."
    }

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
