import { createBrowserRouter, Navigate, type RouteObject } from 'react-router'

import { ConfirmEmailPage } from '@/features/auth/ConfirmEmailPage'
import { LoginPage } from '@/features/auth/LoginPage'
import { RegisterPage } from '@/features/auth/RegisterPage'
import { TwoFactorPage } from '@/features/auth/TwoFactorPage'
import { BillingPage } from '@/features/billing/BillingPage'
import {
  BillingCancelPage,
  BillingSuccessPage,
} from '@/features/billing/BillingResultPages'
import { DocumentsPage } from '@/features/documents/DocumentsPage'
import { DocumentTypesPage } from '@/features/documents/DocumentTypesPage'
import { FolderPage } from '@/features/documents/FolderPage'
import { ProfilePage } from '@/features/profile/ProfilePage'
import { NotificationPage } from '@/features/notifications/NotificationPage'
import { NotificationsPage } from '@/features/notifications/NotificationsPage'
import { PublicUploadPage } from '@/features/requests/PublicUploadPage'
import { RequestsPage } from '@/features/requests/RequestsPage'
import { SecurityPage } from '@/features/security/SecurityPage'
import { AuthLayout } from '@/layouts/AuthLayout'
import { MainLayout } from '@/layouts/MainLayout'
import { ErrorPage } from '@/pages/ErrorPage'
import { NotFoundPage } from '@/pages/NotFoundPage'

import { GuestRoute, ProtectedRoute } from './guards'
import { paths } from './paths'
import { RootLayout } from './RootLayout'

export const routes: RouteObject[] = [
  {
    // Tab titles from route handles; a crash anywhere shows ErrorPage
    element: <RootLayout />,
    errorElement: <ErrorPage />,
    children: [
      {
        element: <AuthLayout />,
        children: [
          // Guests only: a signed-in user is redirected into the app
          {
            element: <GuestRoute />,
            children: [
              {
                path: paths.login,
                element: <LoginPage />,
                handle: { title: 'Log in' },
              },
              {
                path: paths.register,
                element: <RegisterPage />,
                handle: { title: 'Sign up' },
              },
              {
                path: paths.twoFactor,
                element: <TwoFactorPage />,
                handle: { title: 'Two-factor authentication' },
              },
            ],
          },
          // Public: opened from email links, signed in or not
          {
            path: paths.confirmEmail,
            element: <ConfirmEmailPage />,
            handle: { title: 'Confirm email' },
          },
          {
            path: paths.upload,
            element: <PublicUploadPage />,
            handle: { title: 'Upload document' },
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
                element: <DocumentsPage />,
                handle: { title: 'My documents' },
              },
              {
                path: paths.folder,
                element: <FolderPage />,
                handle: { title: 'Folder' },
              },
              {
                path: paths.documentTypes,
                element: <DocumentTypesPage />,
                handle: { title: 'Document types' },
              },
              {
                path: paths.requests,
                element: <RequestsPage />,
                handle: { title: 'Document requests' },
              },
              {
                path: paths.notifications,
                element: <NotificationsPage />,
                handle: { title: 'Notifications' },
              },
              {
                path: paths.notification,
                element: <NotificationPage />,
                handle: { title: 'Notification' },
              },
              {
                path: paths.billing,
                element: <BillingPage />,
                handle: { title: 'Plans & billing' },
              },
              {
                path: paths.billingSuccess,
                element: <BillingSuccessPage />,
                handle: { title: 'Payment successful' },
              },
              {
                path: paths.billingCancel,
                element: <BillingCancelPage />,
                handle: { title: 'Payment canceled' },
              },
              {
                path: paths.profile,
                element: <ProfilePage />,
                handle: { title: 'Profile' },
              },
              {
                path: paths.security,
                element: <SecurityPage />,
                handle: { title: 'Security' },
              },
            ],
          },
        ],
      },
      {
        path: '*',
        element: <NotFoundPage />,
        handle: { title: 'Page not found' },
      },
    ],
  },
]

export const createAppRouter = () => createBrowserRouter(routes)
