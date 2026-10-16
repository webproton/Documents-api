import type { InternalAxiosRequestConfig } from 'axios'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import { tokenStorage } from '@/lib/storage'
import { api, apiError, server } from '@/test/server'

import { apiClient } from './client'

/** Send a request through the interceptors and capture its headers. */
async function captureHeaders() {
  let sent: InternalAxiosRequestConfig | undefined
  await apiClient.get('/ping/', {
    adapter: async (config) => {
      sent = config
      return { data: null, status: 200, statusText: 'OK', headers: {}, config }
    },
  })
  return sent!.headers
}

describe('apiClient', () => {
  it('sends no credentials for a guest', async () => {
    const headers = await captureHeaders()

    expect(headers.get('Authorization')).toBeUndefined()
    expect(headers.get('X-Device-Token')).toBeUndefined()
  })

  it('attaches the access token and trusted-device token', async () => {
    tokenStorage.setTokens('access-123', 'refresh-456')
    tokenStorage.setDeviceToken('device-789')

    const headers = await captureHeaders()

    expect(headers.get('Authorization')).toBe('Bearer access-123')
    expect(headers.get('X-Device-Token')).toBe('device-789')
  })

  it('keeps the device token after the session is cleared', async () => {
    tokenStorage.setTokens('access-123', 'refresh-456')
    tokenStorage.setDeviceToken('device-789')

    tokenStorage.clearSession()
    const headers = await captureHeaders()

    expect(headers.get('Authorization')).toBeUndefined()
    expect(headers.get('X-Device-Token')).toBe('device-789')
  })
})

describe('apiClient token refresh', () => {
  /** Protected endpoint: accepts only the given access token. */
  function protectedEndpoint(validAccess: string) {
    return http.get(api('/documents/types/'), ({ request }) =>
      request.headers.get('Authorization') === `Bearer ${validAccess}`
        ? HttpResponse.json([])
        : apiError(401, { detail: 'Token is invalid or expired' }),
    )
  }

  it('refreshes an expired access token and retries the request', async () => {
    let refreshBody: unknown
    server.use(
      protectedEndpoint('fresh-access'),
      http.post(api('/auth/refresh/'), async ({ request }) => {
        refreshBody = await request.json()
        return HttpResponse.json({
          access: 'fresh-access',
          refresh: 'rotated-refresh',
        })
      }),
    )
    tokenStorage.setTokens('expired-access', 'old-refresh')

    const response = await apiClient.get('/documents/types/')

    expect(response.status).toBe(200)
    expect(refreshBody).toEqual({ refresh: 'old-refresh' })
    // Rotated refresh token replaces the blacklisted one
    expect(tokenStorage.getAccess()).toBe('fresh-access')
    expect(tokenStorage.getRefresh()).toBe('rotated-refresh')
  })

  it('sends one refresh request for parallel 401 responses', async () => {
    let refreshCalls = 0
    server.use(
      protectedEndpoint('fresh-access'),
      http.post(api('/auth/refresh/'), () => {
        refreshCalls += 1
        return HttpResponse.json({ access: 'fresh-access', refresh: 'r2' })
      }),
    )
    tokenStorage.setTokens('expired-access', 'r1')

    await Promise.all([
      apiClient.get('/documents/types/'),
      apiClient.get('/documents/types/'),
      apiClient.get('/documents/types/'),
    ])

    expect(refreshCalls).toBe(1)
  })

  it('does not refresh when a guest request gets 401', async () => {
    // No refresh handler: calling it would fail the test
    server.use(
      http.post(api('/auth/login/'), () =>
        apiError(401, { detail: 'No active account found' }),
      ),
    )

    await expect(apiClient.post('/auth/login/', {})).rejects.toMatchObject({
      response: { status: 401 },
    })
  })
})
