import { useQuery } from '@tanstack/react-query'
import { Link, useSearchParams } from 'react-router'

import { authApi } from '@/api/auth'
import { Alert } from '@/components/ui/Alert'
import { paths } from '@/routes/paths'

/**
 * Landing page for the link in the confirmation email:
 * /confirm-email?token=<uuid> (built by the backend from FRONTEND_URL).
 */
export function ConfirmEmailPage() {
  const [searchParams] = useSearchParams()
  const token = searchParams.get('token')

  // The token is single-use, so the request must run exactly once.
  // useQuery dedupes by key — unlike a mutation in useEffect, it is not
  // sent twice when React StrictMode mounts the component twice.
  const confirmation = useQuery({
    queryKey: ['confirm-email', token],
    queryFn: () => authApi.confirmEmail(token!),
    enabled: Boolean(token),
    retry: false,
    staleTime: Infinity,
    gcTime: Infinity,
  })

  return (
    <div className="flex flex-col gap-4 text-center">
      <h1 className="text-2xl font-semibold">Email confirmation</h1>

      {!token || confirmation.isError ? (
        <>
          <Alert variant="error">
            This confirmation link is invalid, expired or has already been used.
          </Alert>
          <Link
            to={paths.login}
            className="text-sm text-blue-600 hover:underline"
          >
            Go to log in
          </Link>
        </>
      ) : confirmation.isSuccess ? (
        <>
          <Alert variant="success">
            Your email is confirmed. You can log in now.
          </Alert>
          <Link
            to={paths.login}
            className="text-sm text-blue-600 hover:underline"
          >
            Log in
          </Link>
        </>
      ) : (
        <p className="text-slate-600">Confirming your email…</p>
      )}
    </div>
  )
}
