/**
 * Persistent client-side storage for auth tokens.
 *
 * - access / refresh: JWT pair, cleared on logout.
 * - deviceToken: trusted-device token issued after 2FA. It survives logout
 *   (per spec the device stays trusted until it expires or is revoked).
 */
const KEYS = {
  access: 'auth.access',
  refresh: 'auth.refresh',
  deviceToken: 'auth.deviceToken',
} as const

type TokenName = keyof typeof KEYS

function read(name: TokenName): string | null {
  return localStorage.getItem(KEYS[name])
}

function write(name: TokenName, value: string | null): void {
  if (value === null) localStorage.removeItem(KEYS[name])
  else localStorage.setItem(KEYS[name], value)
}

export const tokenStorage = {
  getAccess: () => read('access'),
  getRefresh: () => read('refresh'),
  getDeviceToken: () => read('deviceToken'),

  setTokens(access: string, refresh: string) {
    write('access', access)
    write('refresh', refresh)
  },
  setDeviceToken: (token: string | null) => write('deviceToken', token),

  /** Logout: drop the JWT pair but keep the trusted-device token. */
  clearSession() {
    write('access', null)
    write('refresh', null)
  },
}
