# front

React 19 + TypeScript + Vite. **SPA 전용** (SSR/loader 패턴 사용 안 함).

## 실행

```bash
npm install
npm run dev        # http://localhost:5180
npm run typecheck
npm run build
```

dev 서버는 `/api`, `/ws` 요청을 백엔드로 프록시한다 (호스트 실행 시 `localhost:8010`,
컨테이너 실행 시 백엔드 네트워크의 `web:8000` — `VITE_PROXY_TARGET`으로 제어).
브라우저는 항상 5180 하나만 쓰므로 외부 공개 시 포트포워딩도 5180만 열면 된다.
포트를 바꾸려면 `.env`(FRONT_PORT) + `vite.config.ts` + `package.json`을 함께 수정.

컨테이너로 돌리려면 `docker compose -f docker-compose.dev.yml up -d`
(컨테이너 이름 `climbing-test-front`). 백엔드 스택을 먼저 띄워야 한다 (네트워크 공유).
소스를 마운트하고 폴링 감시를 켜 두어 HMR이 유지된다.

프로덕션은 `Dockerfile.prod` — 빌드 결과를 nginx로 정적 서빙한다.

## 구조

```
src/
  api/          axios 인스턴스(client.ts), snake↔camel 변환(case.ts)
  hooks/        TanStack Query 훅, useChatSocket
  stores/       authStore (access=메모리, refresh=localStorage)
  components/   common/ 부터 도메인별로 추가
  pages/        라우트 단위 화면
  routes.tsx    createBrowserRouter
  index.css     Chalk & Terra 디자인 토큰 (@theme)
```

색상은 `index.css`의 토큰만 사용한다 (임의 hex 금지).
난이도 색만 예외 — `GymDifficulty.color` DB 값을 인라인으로 렌더링한다.
