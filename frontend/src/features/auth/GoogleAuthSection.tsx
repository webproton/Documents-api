import { useMutation } from '@tanstack/react-query'

import { authApi } from '@/api/auth'
import { parseApiError } from '@/api/errors'
import { GoogleSignInButton } from '@/components/GoogleSignInButton'
import { Alert } from '@/components/ui/Alert'
import { getGoogleClientId } from '@/lib/google'

import { useCompleteLogin } from './useCompleteLogin'

interface GoogleAuthSectionProps {
  text?: 'signin_with' | 'signup_with'
}

/**
 * "or" divider + Google button for the login and register pages.
 * The backend creates the account on first sign-in, so both pages use it.
 */
export function GoogleAuthSection({ text }: GoogleAuthSectionProps) {
  const completeLogin = useCompleteLogin()
  const googleAuth = useMutation({
    mutationFn: authApi.googleAuth,
    onSuccess: completeLogin,
  })

  if (!getGoogleClientId()) return null

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-3 text-xs text-slate-400 uppercase">
        <span className="h-px flex-1 bg-slate-200" />
        or
        <span className="h-px flex-1 bg-slate-200" />
      </div>

      {googleAuth.isError && (
        <Alert variant="error">{parseApiError(googleAuth.error).message}</Alert>
      )}
      {googleAuth.isPending && (
        <p className="text-center text-sm text-slate-500">
          Signing in with Google…
        </p>
      )}

      <GoogleSignInButton
        text={text}
        onCredential={(idToken) => googleAuth.mutate(idToken)}
      />
    </div>
  )
}
