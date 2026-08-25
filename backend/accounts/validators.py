"""한국 웹 관행에 맞춘 비밀번호 validator.

settings.AUTH_PASSWORD_VALIDATORS 에 등록되어 validate_password() 경유로 실행된다.
프론트(front/src/lib/validation.ts)의 체크리스트와 규칙을 동일하게 유지할 것.

전체 규칙 (2026-08 확정):
  8~16자 · 영문/숫자/특수문자 2종 이상 조합 · 아이디(이메일·닉네임) 포함 금지
  · 동일 문자 3연속 및 연속 문자열(123, abc) 금지 · 흔한 비밀번호 차단
아이디 포함 금지는 UserAttributeSimilarityValidator, 흔한 비밀번호는
CommonPasswordValidator(Django 내장)가 담당한다.
"""

import re

from django.core.exceptions import ValidationError

PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 16


class MaximumLengthValidator:
    """상한 16자 — 한국 관행. 시리얼라이저 max_length 와 이중 방어."""

    def validate(self, password, user=None):
        if len(password) > PASSWORD_MAX_LENGTH:
            raise ValidationError(
                f"비밀번호는 {PASSWORD_MAX_LENGTH}자 이하여야 합니다.",
                code="password_too_long",
            )

    def get_help_text(self):
        return f"비밀번호는 {PASSWORD_MAX_LENGTH}자 이하여야 합니다."


class CharacterComboValidator:
    """영문 / 숫자 / 특수문자 중 2종 이상 조합."""

    def validate(self, password, user=None):
        classes = sum(
            bool(re.search(pattern, password))
            for pattern in (r"[a-zA-Z]", r"\d", r"[^a-zA-Z0-9\s]")
        )
        if classes < 2:
            raise ValidationError(
                "영문, 숫자, 특수문자 중 2종류 이상을 조합해야 합니다.",
                code="password_no_combo",
            )

    def get_help_text(self):
        return "영문, 숫자, 특수문자 중 2종류 이상을 조합해야 합니다."


class SequentialCharacterValidator:
    """동일 문자 3연속(aaa) 및 연속 문자열(123, abc, cba) 금지."""

    def validate(self, password, user=None):
        if re.search(r"(.)\1\1", password):
            raise ValidationError(
                "같은 문자를 3회 이상 연속 사용할 수 없습니다.",
                code="password_repeated_char",
            )
        lowered = password.lower()
        for i in range(len(lowered) - 2):
            a, b, c = (ord(ch) for ch in lowered[i : i + 3])
            if b - a == c - b and abs(b - a) == 1:
                raise ValidationError(
                    "연속된 문자나 숫자(123, abc)는 사용할 수 없습니다.",
                    code="password_sequential",
                )

    def get_help_text(self):
        return "연속된 문자나 숫자(123, abc)는 사용할 수 없습니다."
