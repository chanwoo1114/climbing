from celery import shared_task
from django.core.mail import send_mail


@shared_task(
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    max_retries=3,
)
def send_email_task(
    subject: str,
    message: str,
    recipient_list: list[str],
    html_message: str | None = None,
):
    """메일 1통 발송 (텍스트 + 선택적 HTML 대체 본문).

    SMTP 일시 장애는 백오프 재시도(최대 3회).
    """
    send_mail(subject, message, None, recipient_list, html_message=html_message)
