"""테스트 공용 헬퍼.

로그인은 이메일 인증이 끝난 계정만 되므로, 로그인이 필요한 테스트는
create_verified_user() 로 만들거나 verify() 로 인증 처리한다.
"""

import re

from django.utils import timezone

from accounts.models import User
from accounts.services import register_user

PASSWORD = "s3cure-pass!"


def verify(user: User) -> User:
    user.email_verified_at = timezone.now()
    user.save(update_fields=["email_verified_at", "updated_at"])
    return user


def create_verified_user(
    email="user@example.com", nickname="유저", password=PASSWORD
) -> User:
    return verify(register_user(email=email, nickname=nickname, password=password))


def extract_query(body: str, name: str) -> str:
    """메일 본문 링크의 쿼리 파라미터 값 (?token=..., &uid=...)."""
    match = re.search(rf"[?&]{name}=([^&\s]+)", body)
    assert match, f"메일 본문에 {name} 파라미터가 없음:\n{body}"
    return match.group(1)
