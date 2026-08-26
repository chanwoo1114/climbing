"""인증/재설정 메일 — 템플릿 렌더링 + 링크 생성. 발송 자체는 Celery(tasks.send_email_task).

템플릿은 accounts/templates/accounts/email/ 에 HTML(.html) 과 텍스트(.txt) 한 쌍씩.
HTML 을 못 보는 클라이언트는 텍스트 본문을 보고, 테스트도 텍스트 본문에서 링크를 읽는다.
"""

from django.conf import settings
from django.template.loader import render_to_string

from accounts.tasks import send_email_task
from accounts.tokens import (
    make_email_verification_token,
    make_password_reset_credentials,
)


def _hours(seconds: int) -> int:
    return max(1, seconds // 3600)


def _dispatch(*, template: str, subject: str, preheader: str, to: str, **context):
    context.update(subject=subject, preheader=preheader)
    text = render_to_string(f"accounts/email/{template}.txt", context)
    html = render_to_string(f"accounts/email/{template}.html", context)
    send_email_task.delay(subject, text, [to], html)


def send_verification_email(user) -> None:
    token = make_email_verification_token(user)
    _dispatch(
        template="verification",
        subject="[Climbing] 이메일 인증을 완료해 주세요",
        preheader="버튼 하나면 가입이 끝나요.",
        to=user.email,
        nickname=user.nickname,
        link=f"{settings.FRONTEND_BASE_URL}/verify-email?token={token}",
        hours=_hours(settings.EMAIL_VERIFICATION_TIMEOUT),
    )


def send_password_reset_email(user) -> None:
    uid, token = make_password_reset_credentials(user)
    _dispatch(
        template="password_reset",
        subject="[Climbing] 비밀번호 재설정 안내",
        preheader="요청하지 않았다면 무시해도 괜찮아요.",
        to=user.email,
        nickname=user.nickname,
        link=f"{settings.FRONTEND_BASE_URL}/reset-password?uid={uid}&token={token}",
        hours=_hours(settings.PASSWORD_RESET_TIMEOUT),
    )
