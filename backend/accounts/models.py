from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.db.models.functions import Lower
from django.utils import timezone

from common.managers import SoftDeleteQuerySet
from common.models import BaseModel


class UserManager(BaseUserManager.from_queryset(SoftDeleteQuerySet)):
    """이메일을 로그인 식별자로 사용.

    다른 모델과 동일하게 objects 는 is_deleted=False 만 반환한다. 이게 없으면
    탈퇴(soft delete)한 계정으로도 인증이 통과한다 — authenticate() 가
    User._default_manager 를 쓰기 때문. 삭제분 포함 조회는 all_objects.
    """

    use_in_migrations = True

    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)

    @classmethod
    def normalize_email(cls, email):
        """이메일 전체를 소문자로 통일한다.

        Django 기본 normalize_email 은 도메인(@ 뒤)만 소문자화해서
        Case@test.com 과 case@test.com 이 별개 계정으로 가입된다.
        로컬파트는 RFC 상 대소문자를 구분하지만 실제 메일 서비스는 구분하지
        않으므로 로그인 ID 용도로는 전부 소문자로 저장한다.
        """
        email = super().normalize_email(email)
        return email.strip().lower() if email else email

    def get_by_natural_key(self, username):
        # authenticate() 경유 로그인 조회. 저장은 소문자로 통일되지만,
        # 정규화 이전에 만들어진 계정도 찾을 수 있게 iexact 로 본다.
        return self.get(**{f"{self.model.USERNAME_FIELD}__iexact": username})

    def _create_user(self, email, password, **extra):
        if not email:
            raise ValueError("이메일은 필수입니다.")
        user = self.model(email=self.normalize_email(email), **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra):
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra)

    def create_superuser(self, email, password=None, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        return self._create_user(email, password, **extra)


class User(AbstractUser, BaseModel):
    username = None
    # verbose_name 은 검증 메시지에 그대로 노출된다
    # ("비밀번호가 이메일와 너무 유사합니다" 처럼).
    email = models.EmailField(
        unique=True, verbose_name="이메일", db_comment="로그인 ID로 쓰는 이메일"
    )
    nickname = models.CharField(
        max_length=30,
        unique=True,
        verbose_name="닉네임",
        db_comment="표시 이름 (중복 불가)",
    )

    email_verified_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="이메일 인증 시각",
        db_comment="인증 메일 링크를 확인한 시각. NULL 이면 미인증 (로그인 불가)",
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["nickname"]

    objects = UserManager()

    class Meta:
        db_table = "accounts_user"
        db_table_comment = "회원 계정 — 이메일 로그인, 닉네임. soft delete 지원"
        # authenticate() 가 참조하는 _default_manager 를 objects 로 못박는다.
        # (매니저 생성 순서에 따라 all_objects 가 잡히면 탈퇴 계정이 로그인된다.)
        default_manager_name = "objects"
        constraints = [
            # 대소문자만 다른 이메일 중복을 DB 에서도 막는다 (동시 가입 경합 대비).
            models.UniqueConstraint(
                Lower("email"), name="accounts_user_email_lower_uniq"
            ),
            # 닉네임도 Casey / casey 를 같은 이름으로 본다 (값은 입력한 대로 저장).
            models.UniqueConstraint(
                Lower("nickname"), name="accounts_user_nickname_lower_uniq"
            ),
        ]

    def __str__(self):
        return self.nickname


class UserProfile(BaseModel):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="profile", db_comment="회원 FK"
    )
    bio = models.TextField(blank=True, db_comment="자기소개")
    image = models.URLField(blank=True, db_comment="프로필 이미지 URL (S3)")
    home_gym = models.ForeignKey(
        "gyms.Gym",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        db_comment="주로 다니는 암장 FK",
    )
    # 여러 크루에 가입할 수 있지만 프로필에 내세우는 대표 크루는 1개 (docs/개발정의.md 4장).
    main_crew = models.ForeignKey(
        "crews.Crew",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="main_profiles",
        db_comment="대표 크루 FK (활동 중인 크루 중 1개). 탈퇴·강퇴·크루 삭제 시 NULL",
    )

    class Meta:
        db_table_comment = "회원 프로필 — 소개글/이미지/홈짐. User와 1:1"

    def __str__(self):
        return f"{self.user.nickname} 프로필"


class SocialAccount(BaseModel):
    """소셜 로그인 연결 (카카오). 한 회원이 provider 별로 하나씩.

    provider 의 access/refresh 토큰은 저장하지 않는다 (docs/개발정의.md 5장 5번).
    로그인은 매번 인가 코드를 서버에서 교환해 프로필만 읽고 토큰은 버린다.
    연결 해제는 soft delete — 같은 카카오 계정을 다시 연결하면 새 행이 생긴다.
    """

    class Provider(models.TextChoices):
        KAKAO = "kakao", "카카오"

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="social_accounts",
        db_comment="회원 FK",
    )
    provider = models.CharField(
        max_length=20, choices=Provider.choices, db_comment="소셜 제공자 (kakao)"
    )
    provider_uid = models.CharField(
        max_length=64, db_comment="제공자 쪽 사용자 ID (카카오 회원번호)"
    )
    email_at_provider = models.EmailField(
        blank=True, db_comment="연결 당시 제공자에 등록된 이메일 (참고용)"
    )
    nickname_at_provider = models.CharField(
        max_length=100, blank=True, db_comment="연결 당시 제공자 닉네임 (참고용)"
    )
    connected_at = models.DateTimeField(
        default=timezone.now, db_comment="연결(최초 로그인) 시각"
    )

    class Meta:
        db_table_comment = "소셜 로그인 연결 — provider 토큰은 저장하지 않는다"
        constraints = [
            # 살아 있는 연결 기준으로만 유일. 해제(soft delete)한 뒤 재연결을 허용한다.
            models.UniqueConstraint(
                fields=["provider", "provider_uid"],
                condition=models.Q(is_deleted=False),
                name="accounts_socialaccount_provider_uid_uniq",
            )
        ]

    def __str__(self):
        return f"{self.user.nickname} ↔ {self.get_provider_display()}"
