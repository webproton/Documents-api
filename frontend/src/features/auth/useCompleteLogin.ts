import { useCallback } from 'react'
import { useLocation, useNavigate } from 'react-router'

import type { GoogleAuthResponse, LoginResponse } from '@/api/auth'
import type { RedirectState } from '@/routes/guards'
import { paths } from '@/routes/paths'

import { useAuth } from './auth-context'
import type { TwoFactorState } from './two-factor'

/**
 * Finish the first login step (password or Google):
 * tokens → start the session; requires_2fa → continue on the 2FA page.
 */
export function useCompleteLogin() {
  const { signIn } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  return useCallback(
    (data: LoginResponse | GoogleAuthResponse) => {
      if (data.requires_2fa) {
        const state: TwoFactorState = {
          preAuthToken: data.pre_auth_token,
          deliveryMethod: data.delivery_method,
          message: data.message,
          // Keep the originally requested page through the 2FA step
          from: (location.state as RedirectState | null)?.from,
        }
        navigate(paths.twoFactor, { state })
        return
      }
      signIn(data)
    },
    [location.state, navigate, signIn],
  )
}
