import { createBrowserRouter } from 'react-router'

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
      // TODO: GymDetail, Feed, LogCreate, Profile,
      //       ChatList, ChatRoom, Board, PostDetail, CrewList, AnalysisResult
    ],
  },
])
