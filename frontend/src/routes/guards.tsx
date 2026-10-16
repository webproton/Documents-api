import { Navigate, Outlet, useLocation, type Location } from 'react-router'

import { useAuth } from '@/features/auth/auth-context'

import { paths } from './paths'

/** Router state used to return the user to the page they originally opened. */
export interface RedirectState {
  from?: Location
}

/** Authenticated pages: guests are sent to login and come back afterwards. */
export function ProtectedRoute() {
  const { isAuthenticated } = useAuth()
  const location = useLocation()

  if (!isAuthenticated) {
    return (
      <Navigate
        to={paths.login}
        replace
        state={{ from: location } satisfies RedirectState}
      />
    )
  }
  return <Outlet />
}

/** Login / register / 2FA: a signed-in user goes back to the app. */
export function GuestRoute() {
  const { isAuthenticated } = useAuth()
  const location = useLocation()

  if (isAuthenticated) {
    const from = (location.state as RedirectState | null)?.from
    return <Navigate to={from ?? paths.documents} replace />
  }
  return <Outlet />
}
