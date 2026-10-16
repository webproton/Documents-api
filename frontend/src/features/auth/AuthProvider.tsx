import { useQueryClient } from '@tanstack/react-query'
import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'

import { authApi, type SessionTokens } from '@/api/auth'
import { setSessionExpiredHandler } from '@/api/client'
import { tokenStorage } from '@/lib/storage'

import { AuthContext } from './auth-context'

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()
  const [isAuthenticated, setIsAuthenticated] = useState(() =>
    Boolean(tokenStorage.getAccess()),
  )

  const endSession = useCallback(() => {
    tokenStorage.clearSession()
    // Drop cached data of the previous user
    queryClient.clear()
    setIsAuthenticated(false)
  }, [queryClient])

  // Refresh token expired or was revoked → back to login
  useEffect(() => {
    setSessionExpiredHandler(endSession)
    return () => setSessionExpiredHandler(() => {})
  }, [endSession])

  const signIn = useCallback((session: SessionTokens) => {
    tokenStorage.setTokens(session.access, session.refresh)
    // Identifies this browser's session on the server (and trust for 2FA)
    tokenStorage.setDeviceToken(session.device_token)
    // GuestRoute then redirects to the originally requested page
    setIsAuthenticated(true)
  }, [])

  const signOut = useCallback(async () => {
    const refresh = tokenStorage.getRefresh()
    try {
      if (refresh) await authApi.logout(refresh)
    } catch {
      // Logout locally even if the server call fails (e.g. token already expired)
    }
    endSession()
  }, [endSession])

  const value = useMemo(
    () => ({ isAuthenticated, signIn, signOut }),
    [isAuthenticated, signIn, signOut],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
