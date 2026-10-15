import { createBrowserRouter, Navigate, type RouteObject } from 'react-router'

import { AuthLayout } from '@/layouts/AuthLayout'
import { MainLayout } from '@/layouts/MainLayout'
import { NotFoundPage } from '@/pages/NotFoundPage'
import { PlaceholderPage } from '@/pages/PlaceholderPage'

import { paths } from './paths'

// Placeholders are replaced by real pages stage by stage.
// Route guards (ProtectedRoute / GuestRoute) are added in FE-02.
export const routes: RouteObject[] = [
  {
    element: <AuthLayout />,
    children: [
      {
        path: paths.login,
        element: <PlaceholderPage title="Log in" stage="FE-02" />,
      },
      {
        path: paths.register,
        element: <PlaceholderPage title="Sign up" stage="FE-02" />,
      },
      {
        path: paths.confirmEmail,
        element: <PlaceholderPage title="Confirm email" stage="FE-02" />,
      },
      {
        path: paths.twoFactor,
        element: (
          <PlaceholderPage title="Two-factor authentication" stage="FE-03" />
        ),
      },
      {
        path: paths.upload,
        element: <PlaceholderPage title="Upload document" stage="FE-09" />,
      },
    ],
  },
  {
    element: <MainLayout />,
    children: [
      { path: paths.home, element: <Navigate to={paths.documents} replace /> },
      {
        path: paths.documents,
        element: <PlaceholderPage title="My documents" stage="FE-08" />,
      },
      {
        path: paths.folder,
        element: <PlaceholderPage title="Folder" stage="FE-08" />,
      },
      {
        path: paths.documentTypes,
        element: <PlaceholderPage title="Document types" stage="FE-07" />,
      },
      {
        path: paths.requests,
        element: <PlaceholderPage title="Document requests" stage="FE-09" />,
      },
      {
        path: paths.notifications,
        element: <PlaceholderPage title="Notifications" stage="FE-11" />,
      },
      {
        path: paths.billing,
        element: <PlaceholderPage title="Plans & billing" stage="FE-10" />,
      },
      {
        path: paths.billingSuccess,
        element: <PlaceholderPage title="Payment successful" stage="FE-10" />,
      },
      {
        path: paths.billingCancel,
        element: <PlaceholderPage title="Payment canceled" stage="FE-10" />,
      },
      {
        path: paths.profile,
        element: <PlaceholderPage title="Profile" stage="FE-05" />,
      },
      {
        path: paths.security,
        element: <PlaceholderPage title="Security" stage="FE-06" />,
      },
    ],
  },
  { path: '*', element: <NotFoundPage /> },
]

export const createAppRouter = () => createBrowserRouter(routes)
