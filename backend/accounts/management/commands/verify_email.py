"""개발용: 메일 없이 계정을 인증 완료 처리한다.

    python manage.py verify_email user@example.com

로컬에서는 메일이 콘솔(celery 로그)로만 찍히므로 링크를 복사하기 번거로울 때 쓴다.
"""

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from accounts.models import User


class Command(BaseCommand):
    help = "이메일 인증을 완료 처리한다 (개발용)"

    def add_arguments(self, parser):
        parser.add_argument("email")

    def handle(self, *args, **options):
        user = User.objects.filter(email__iexact=options["email"]).first()
        if user is None:
            raise CommandError(f"계정 없음: {options['email']}")
        if user.email_verified_at:
            self.stdout.write(f"이미 인증됨: {user.email} ({user.email_verified_at})")
            return
        user.email_verified_at = timezone.now()
        user.save(update_fields=["email_verified_at", "updated_at"])
        self.stdout.write(self.style.SUCCESS(f"인증 완료: {user.email}"))
