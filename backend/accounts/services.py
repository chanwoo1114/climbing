from django.db import transaction

from accounts.models import User, UserProfile


@transaction.atomic
def register_user(*, email: str, nickname: str, password: str) -> User:
    """유저 + 빈 프로필을 한 트랜잭션으로 생성한다."""
    user = User.objects.create_user(email=email, nickname=nickname, password=password)
    UserProfile.objects.create(user=user)
    return user
