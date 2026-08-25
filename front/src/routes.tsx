import { createBrowserRouter } from 'react-router'

import RootLayout from '@/components/common/RootLayout'
import Login from '@/pages/Login'
import MapHome from '@/pages/MapHome'
import Signup from '@/pages/Signup'

// React Router v7 라이브러리 모드 — loader/action 패턴은 쓰지 않는다.
export const router = createBrowserRouter([
  {
    path: '/',
    element: <RootLayout />,
    children: [
      { index: true, element: <MapHome /> },
      { path: 'login', element: <Login /> },
      { path: 'signup', element: <Signup /> },
      // TODO: GymDetail, Feed, LogCreate, Profile,
      //       ChatList, ChatRoom, Board, PostDetail, CrewList, AnalysisResult
    ],
  },
])
