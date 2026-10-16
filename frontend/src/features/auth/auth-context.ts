import { createContext, useContext } from 'react'

import type { SessionTokens } from '@/api/auth'

export interface AuthContextValue {
  isAuthenticated: boolean
  /** Save JWT pair + device session token after login / 2FA / Google. */
  signIn: (session: SessionTokens) => void
  /** Blacklist the refresh token and drop the session (device token stays). */
  signOut: () => Promise<void>
}

export const AuthContext = createContext<AuthContextValue | null>(null)

export function useAuth(): AuthContextValue {
  const value = useContext(AuthContext)
  if (!value) throw new Error('useAuth must be used inside <AuthProvider>')
  return value
}
