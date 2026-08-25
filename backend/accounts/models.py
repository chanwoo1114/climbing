from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models

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

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["nickname"]

    objects = UserManager()

    class Meta:
        db_table = "accounts_user"
        db_table_comment = "회원 계정 — 이메일 로그인, 닉네임. soft delete 지원"
        # authenticate() 가 참조하는 _default_manager 를 objects 로 못박는다.
        # (매니저 생성 순서에 따라 all_objects 가 잡히면 탈퇴 계정이 로그인된다.)
        default_manager_name = "objects"

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
    # TODO(M6): 대표 크루는 1개 (docs/개발정의.md 4장)
    # main_crew = models.ForeignKey(
    #     "crews.Crew", null=True, blank=True, on_delete=models.SET_NULL
    # )

    class Meta:
        db_table_comment = "회원 프로필 — 소개글/이미지/홈짐. User와 1:1"

    def __str__(self):
        return f"{self.user.nickname} 프로필"
