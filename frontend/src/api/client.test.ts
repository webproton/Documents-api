import type { InternalAxiosRequestConfig } from 'axios'
import { describe, expect, it } from 'vitest'

import { tokenStorage } from '@/lib/storage'

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
