import { createBrowserRouter, Navigate, type RouteObject } from 'react-router'

import { ConfirmEmailPage } from '@/features/auth/ConfirmEmailPage'
import { LoginPage } from '@/features/auth/LoginPage'
import { RegisterPage } from '@/features/auth/RegisterPage'
import { AuthLayout } from '@/layouts/AuthLayout'
import { MainLayout } from '@/layouts/MainLayout'
import { NotFoundPage } from '@/pages/NotFoundPage'
import { PlaceholderPage } from '@/pages/PlaceholderPage'

import { GuestRoute, ProtectedRoute } from './guards'
import { paths } from './paths'

// Placeholders are replaced by real pages stage by stage.
export const routes: RouteObject[] = [
  {
    element: <AuthLayout />,
    children: [
      // Guests only: a signed-in user is redirected into the app
      {
        element: <GuestRoute />,
        children: [
          { path: paths.login, element: <LoginPage /> },
          { path: paths.register, element: <RegisterPage /> },
          {
            path: paths.twoFactor,
            element: (
              <PlaceholderPage
                title="Two-factor authentication"
                stage="FE-03"
              />
            ),
          },
        ],
      },
      // Public: opened from email links, signed in or not
      { path: paths.confirmEmail, element: <ConfirmEmailPage /> },
      {
        path: paths.upload,
        element: <PlaceholderPage title="Upload document" stage="FE-09" />,
      },
    ],
  },
  // Signed-in users only: guests are sent to login
  {
    element: <ProtectedRoute />,
    children: [
      {
        element: <MainLayout />,
        children: [
          {
            path: paths.home,
            element: <Navigate to={paths.documents} replace />,
          },
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
            element: (
              <PlaceholderPage title="Document requests" stage="FE-09" />
            ),
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
            element: (
              <PlaceholderPage title="Payment successful" stage="FE-10" />
            ),
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
    ],
  },
  { path: '*', element: <NotFoundPage /> },
]

export const createAppRouter = () => createBrowserRouter(routes)
