import axios, { isAxiosError, type InternalAxiosRequestConfig } from 'axios'

import { tokenStorage } from '@/lib/storage'

import type { AuthTokens } from './auth'

const baseURL = import.meta.env.VITE_API_URL ?? '/api'

/** Shared axios instance for all Django API calls. */
export const apiClient = axios.create({ baseURL })

// Attach credentials to every request.
// X-Device-Token lets the backend skip 2FA on a trusted device and mark
// the current device in /devices/ (see accounts.utils.extract_raw_device_token).
apiClient.interceptors.request.use((config) => {
  const access = tokenStorage.getAccess()
  const deviceToken = tokenStorage.getDeviceToken()

  if (access) config.headers.set('Authorization', `Bearer ${access}`)
  if (deviceToken) config.headers.set('X-Device-Token', deviceToken)

  return config
})

// ---------------------------------------------------------------------------
// Access token refresh
// ---------------------------------------------------------------------------

let sessionExpiredHandler: () => void = () => {}

/** Called once refresh fails — AuthProvider uses it to log the user out. */
export function setSessionExpiredHandler(handler: () => void) {
  sessionExpiredHandler = handler
}

// Shared promise: parallel 401s trigger a single refresh request
let refreshPromise: Promise<void> | null = null

async function refreshTokens(): Promise<void> {
  const refresh = tokenStorage.getRefresh()
  if (!refresh) throw new Error('No refresh token')

  // Plain axios: the refresh call must not go through these interceptors
  const { data } = await axios.post<AuthTokens>(`${baseURL}/auth/refresh/`, {
    refresh,
  })
  // ROTATE_REFRESH_TOKENS is on: the old refresh token is blacklisted
  tokenStorage.setTokens(data.access, data.refresh)
}

type RetriableConfig = InternalAxiosRequestConfig & { _retried?: boolean }

apiClient.interceptors.response.use(undefined, async (error: unknown) => {
  if (!isAxiosError(error) || error.response?.status !== 401) throw error

  const original = error.config as RetriableConfig | undefined
  // Refresh only requests that were sent with an access token;
  // a 401 from login/2FA means wrong credentials, not an expired session.
  if (!original || original._retried || !original.headers.has('Authorization'))
    throw error

  original._retried = true
  try {
    refreshPromise ??= refreshTokens().finally(() => {
      refreshPromise = null
    })
    await refreshPromise
  } catch {
    tokenStorage.clearSession()
    sessionExpiredHandler()
    throw error
  }

  // Request interceptor puts the new access token on the retry
  return apiClient(original)
})
