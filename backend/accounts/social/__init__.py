"""소셜 로그인 (카카오) — 인가 코드 서버 교환 방식.

프론트는 카카오 토큰을 절대 보지 않고, 서버도 provider 토큰을 저장하지 않는다.
  1. GET  /api/v1/auth/kakao/authorize/  → {authorize_url, state}
  2. 브라우저가 authorize_url 로 이동, 카카오가 KAKAO_REDIRECT_URI 로 ?code=&state= 리다이렉트
  3. POST /api/v1/auth/kakao/callback/ {code, state} → 우리 JWT {access, refresh, is_new}
"""
