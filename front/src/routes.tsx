import { createBrowserRouter } from 'react-router'

import RequireAuth from '@/components/common/RequireAuth'
import RootLayout from '@/components/common/RootLayout'
import ForgotPassword from '@/pages/ForgotPassword'
import Login from '@/pages/Login'
import MapHome from '@/pages/MapHome'
import ResetPassword from '@/pages/ResetPassword'
import Signup from '@/pages/Signup'
import SignupSent from '@/pages/SignupSent'
import VerifyEmail from '@/pages/VerifyEmail'

// React Router v7 라이브러리 모드 — loader/action 패턴은 쓰지 않는다.
export const router = createBrowserRouter([
  {
    path: '/',
    element: <RootLayout />,
    children: [
      { index: true, element: <MapHome /> },
      { path: 'login', element: <Login /> },
      { path: 'signup', element: <Signup /> },
      { path: 'signup/sent', element: <SignupSent /> },
      // 아래 두 경로는 메일 링크가 가리킨다 (backend FRONTEND_BASE_URL + 경로).
      { path: 'verify-email', element: <VerifyEmail /> },
      { path: 'forgot-password', element: <ForgotPassword /> },
      { path: 'reset-password', element: <ResetPassword /> },
      {
        // 로그인 필요 — 비로그인이면 /login 으로, 로그인 후 원래 경로로 복귀
        element: <RequireAuth />,
        children: [
          // TODO(M2~): LogCreate, Profile, ChatList, ChatRoom, CrewList, AnalysisResult
        ],
      },
      // TODO: GymDetail, Feed, Board, PostDetail (공개)
    ],
  },
])
