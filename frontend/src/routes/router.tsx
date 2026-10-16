import { createBrowserRouter, Navigate, type RouteObject } from 'react-router'

import { ConfirmEmailPage } from '@/features/auth/ConfirmEmailPage'
import { LoginPage } from '@/features/auth/LoginPage'
import { RegisterPage } from '@/features/auth/RegisterPage'
import { TwoFactorPage } from '@/features/auth/TwoFactorPage'
import { DocumentsPage } from '@/features/documents/DocumentsPage'
import { DocumentTypesPage } from '@/features/documents/DocumentTypesPage'
import { FolderPage } from '@/features/documents/FolderPage'
import { ProfilePage } from '@/features/profile/ProfilePage'
import { PublicUploadPage } from '@/features/requests/PublicUploadPage'
import { RequestsPage } from '@/features/requests/RequestsPage'
import { SecurityPage } from '@/features/security/SecurityPage'
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
          { path: paths.twoFactor, element: <TwoFactorPage /> },
        ],
      },
      // Public: opened from email links, signed in or not
      { path: paths.confirmEmail, element: <ConfirmEmailPage /> },
      { path: paths.upload, element: <PublicUploadPage /> },
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
            element: <DocumentsPage />,
          },
          {
            path: paths.folder,
            element: <FolderPage />,
          },
          {
            path: paths.documentTypes,
            element: <DocumentTypesPage />,
          },
          { path: paths.requests, element: <RequestsPage /> },
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
            element: <ProfilePage />,
          },
          {
            path: paths.security,
            element: <SecurityPage />,
          },
        ],
      },
    ],
  },
  { path: '*', element: <NotFoundPage /> },
]

export const createAppRouter = () => createBrowserRouter(routes)
