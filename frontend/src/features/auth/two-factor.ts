import type { TwoFactorMethod } from '@/api/auth'
import type { RedirectState } from '@/routes/guards'

/** Router state passed from the login page when the backend answers 202. */
export interface TwoFactorState extends RedirectState {
  preAuthToken: string
  deliveryMethod: TwoFactorMethod
  message: string
}

/** Mirrors TWO_FACTOR_RESEND_COOLDOWN in Django settings. */
export const RESEND_COOLDOWN_SECONDS = 60

/**
 * Whether a 2FA error means the session is gone (3 failed attempts or the
 * 20-minute lifetime expired) and the user must log in again.
 *
 * The backend has no error codes for this, only messages from
 * TwoFactorRedisManager — both end with "Please log in again.".
 */
export function isTwoFactorSessionEnded(message: string): boolean {
  return message.toLowerCase().includes('log in again')
}
