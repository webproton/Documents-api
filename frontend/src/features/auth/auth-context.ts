import { createContext, useContext } from 'react'

import type { AuthTokens } from '@/api/auth'

export interface AuthContextValue {
  isAuthenticated: boolean
  /** Save JWT pair after login / 2FA / social auth. */
  signIn: (tokens: AuthTokens) => void
  /** Blacklist the refresh token and drop the session (device token stays). */
  signOut: () => Promise<void>
}

export const AuthContext = createContext<AuthContextValue | null>(null)

export function useAuth(): AuthContextValue {
  const value = useContext(AuthContext)
  if (!value) throw new Error('useAuth must be used inside <AuthProvider>')
  return value
}
