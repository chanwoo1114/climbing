"""WebSocket 용 JWT 인증 미들웨어.

브라우저 WebSocket 은 Authorization 헤더를 못 붙이므로 access 토큰을
``?token=`` 쿼리로 받는다. 검증에 실패하면 scope["user"] 는 AnonymousUser 로 두고
컨슈머가 연결을 거절한다 (여기서 close 하면 URLRouter 까지 못 가서 코드가 안 남는다).
"""

from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import AuthenticationFailed, InvalidToken


@database_sync_to_async
def _user_from_token(raw_token: str):
    auth = JWTAuthentication()
    try:
        validated = auth.get_validated_token(raw_token)
        return auth.get_user(validated)
    except (InvalidToken, AuthenticationFailed):
        return AnonymousUser()


class JWTAuthMiddleware(BaseMiddleware):
    async def __call__(self, scope, receive, send):
        query = parse_qs(scope.get("query_string", b"").decode())
        token = (query.get("token") or [""])[0]
        scope["user"] = await _user_from_token(token) if token else AnonymousUser()
        return await super().__call__(scope, receive, send)
