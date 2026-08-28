import { createBrowserRouter } from 'react-router'

import RequireAuth from '@/components/common/RequireAuth'
import RootLayout from '@/components/common/RootLayout'
import BetaCreate from '@/pages/BetaCreate'
import BetaDetail from '@/pages/BetaDetail'
import ChatRoom from '@/pages/ChatRoom'
import ChatRooms from '@/pages/ChatRooms'
import CrewCreate from '@/pages/CrewCreate'
import CrewDetail from '@/pages/CrewDetail'
import CrewList from '@/pages/CrewList'
import CrewRanking from '@/pages/CrewRanking'
import Feed from '@/pages/Feed'
import ForgotPassword from '@/pages/ForgotPassword'
import GymDetail from '@/pages/GymDetail'
import GymManage from '@/pages/GymManage'
import KakaoCallback from '@/pages/KakaoCallback'
import LogCreate from '@/pages/LogCreate'
import LogDetail from '@/pages/LogDetail'
import Login from '@/pages/Login'
import ManagedGyms from '@/pages/ManagedGyms'
import MapHome from '@/pages/MapHome'
import MyLogs from '@/pages/MyLogs'
import NotFound from '@/pages/NotFound'
import Notifications from '@/pages/Notifications'
import PostCreate from '@/pages/PostCreate'
import PostDetail from '@/pages/PostDetail'
import PostList from '@/pages/PostList'
import Profile from '@/pages/Profile'
import ResetPassword from '@/pages/ResetPassword'
import Settings from '@/pages/Settings'
import Signup from '@/pages/Signup'
import SignupSent from '@/pages/SignupSent'
import UserFollowList from '@/pages/UserFollowList'
import UserProfile from '@/pages/UserProfile'
import UserSearch from '@/pages/UserSearch'
import VerifyEmail from '@/pages/VerifyEmail'

// React Router v7 라이브러리 모드 — loader/action 패턴은 쓰지 않는다.
export const router = createBrowserRouter([
  {
    path: '/',
    element: <RootLayout />,
    // RootLayout 자체가 깨졌을 때의 마지막 안전망 (헤더 없이 뜬다)
    errorElement: <NotFound />,
    children: [
      {
        // 페이지 렌더 중 오류·Response(404) 는 여기서 받아 헤더는 남긴 채 안내를 띄운다
        errorElement: <NotFound />,
        children: [
          { index: true, element: <MapHome /> },
          // 암장 상세 + 리뷰 읽기는 공개. 리뷰 작성만 페이지 안에서 로그인 여부를 본다.
          { path: 'gyms/:id', element: <GymDetail /> },
          // 베타 영상 읽기는 공개 (조회수는 서버가 올린다). 작성·수정은 아래 RequireAuth 안
          { path: 'betas/:betaId', element: <BetaDetail /> },
          { path: 'login', element: <Login /> },
          { path: 'signup', element: <Signup /> },
          { path: 'signup/sent', element: <SignupSent /> },
          // 아래 두 경로는 메일 링크가 가리킨다 (backend FRONTEND_BASE_URL + 경로).
          { path: 'verify-email', element: <VerifyEmail /> },
          { path: 'forgot-password', element: <ForgotPassword /> },
          { path: 'reset-password', element: <ResetPassword /> },
          // 카카오 인가 페이지가 돌아오는 곳 (backend KAKAO_REDIRECT_URI). 공개 라우트.
          { path: 'auth/kakao/callback', element: <KakaoCallback /> },
          {
            // 로그인 필요 — 비로그인이면 /login 으로, 로그인 후 원래 경로로 복귀
            element: <RequireAuth />,
            children: [
              { path: 'profile', element: <Profile /> },
              // 계정 설정 — 알림·푸시 구독·비밀번호 변경·회원 탈퇴
              { path: 'settings', element: <Settings /> },
              // 암장 관리자 — 내가 관리하는 암장 목록과 관리 화면.
              // 'gyms/managed' 는 정적 세그먼트라 위의 공개 라우트 'gyms/:id' 보다 먼저 매칭된다.
              { path: 'gyms/managed', element: <ManagedGyms /> },
              { path: 'gyms/:id/manage', element: <GymManage /> },
              // 피드·기록은 로그인 전용 (남의 비공개 기록은 서버가 404 로 숨긴다)
              { path: 'feed', element: <Feed /> },
              { path: 'logs', element: <MyLogs /> },
              { path: 'logs/new', element: <LogCreate /> },
              { path: 'logs/:id', element: <LogDetail /> },
              { path: 'logs/:id/edit', element: <LogCreate /> },
              // 베타 영상 올리기·수정 — 한 컴포넌트가 :gymId(생성) / :betaId(수정) 로 갈린다
              { path: 'gyms/:gymId/betas/new', element: <BetaCreate /> },
              { path: 'betas/:betaId/edit', element: <BetaCreate /> },
              // 게시판 — 목록·상세·댓글·모집 참여 모두 로그인 전용 API
              { path: 'posts', element: <PostList /> },
              { path: 'posts/new', element: <PostCreate /> },
              { path: 'posts/:id', element: <PostDetail /> },
              { path: 'posts/:id/edit', element: <PostCreate /> },
              // 회원 — 프로필·팔로우 목록·검색은 모두 로그인 전용 API
              { path: 'users/search', element: <UserSearch /> },
              { path: 'users/:id', element: <UserProfile /> },
              { path: 'users/:id/followers', element: <UserFollowList kind="followers" /> },
              { path: 'users/:id/following', element: <UserFollowList kind="following" /> },
              // 채팅 — 목록·방 모두 참여자 전용 API (WebSocket 은 useChatSocket 훅만)
              { path: 'chat', element: <ChatRooms /> },
              { path: 'chat/rooms/:id', element: <ChatRoom /> },
              // 크루 — 목록·상세·생성·설정 모두 로그인 전용 API
              { path: 'crews', element: <CrewList /> },
              { path: 'crews/new', element: <CrewCreate /> },
              // 정적 세그먼트가 :id 보다 우선하지만, 'ranking' 이 id 로 잡히지 않게 앞에 둔다
              { path: 'crews/ranking', element: <CrewRanking /> },
              { path: 'crews/:id', element: <CrewDetail /> },
              { path: 'crews/:id/edit', element: <CrewCreate /> },
              // 알림 — 로그인 전용 (WebSocket 은 useNotificationSocket 훅만, RootLayout 에서 한 번)
              { path: 'notifications', element: <Notifications /> },
              // TODO(M3~): AnalysisResult
            ],
          },
          { path: '*', element: <NotFound /> },
        ],
      },
    ],
  },
])
