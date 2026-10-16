import { act, screen } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { GoogleCredentialResponse } from '@/lib/google'
import { tokenStorage } from '@/lib/storage'
import { api, apiError, server } from '@/test/server'
import { renderApp } from '@/test/utils'

/**
 * Fake Google Identity Services: renders a stub button and lets the test
 * play the user picking a Google account via pickAccount().
 */
function installFakeGoogle() {
  let callback: ((response: GoogleCredentialResponse) => void) | undefined
  const initialize = vi.fn((config: { callback: typeof callback }) => {
    callback = config.callback
  })
  const renderButton = vi.fn((parent: HTMLElement) => {
    parent.innerHTML = '<button>Sign in with Google</button>'
  })
  window.google = { accounts: { id: { initialize, renderButton } } }

  return {
    initialize,
    pickAccount: (credential: string) => act(() => callback?.({ credential })),
  }
}

describe('Google sign-in', () => {
  beforeEach(() => {
    vi.stubEnv(
      'VITE_GOOGLE_CLIENT_ID',
      'test-client.apps.googleusercontent.com',
    )
  })

  afterEach(() => {
    vi.unstubAllEnvs()
    delete window.google
  })

  it('initializes Google with the client id on the login page', async () => {
    const google = installFakeGoogle()
    renderApp('/login')

    expect(
      await screen.findByRole('button', { name: 'Sign in with Google' }),
    ).toBeInTheDocument()
    expect(google.initialize).toHaveBeenCalledWith(
      expect.objectContaining({
        client_id: 'test-client.apps.googleusercontent.com',
      }),
    )
  })

  it('exchanges the Google ID token for a session', async () => {
    let body: unknown
    server.use(
      http.post(api('/auth/social/google/'), async ({ request }) => {
        body = await request.json()
        return HttpResponse.json({
          access: 'google-access',
          refresh: 'google-refresh',
          id: 7,
          email: 'jane@gmail.com',
        })
      }),
    )
    const google = installFakeGoogle()
    const { router } = renderApp('/register')
    await screen.findByRole('button', { name: 'Sign in with Google' })

    await google.pickAccount('google-id-token')

    expect(
      await screen.findByRole('heading', { name: 'My documents' }),
    ).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/documents')
    expect(body).toEqual({ id_token: 'google-id-token' })
    expect(tokenStorage.getAccess()).toBe('google-access')
  })

  it('continues to the 2FA step when the backend requires it', async () => {
    server.use(
      http.post(api('/auth/social/google/'), () =>
        HttpResponse.json(
          {
            requires_2fa: true,
            pre_auth_token: 'pre-auth-google',
            delivery_method: 'EMAIL',
            message: 'Verification code has been sent to your email.',
          },
          { status: 202 },
        ),
      ),
    )
    const google = installFakeGoogle()
    const { router } = renderApp('/login')
    await screen.findByRole('button', { name: 'Sign in with Google' })

    await google.pickAccount('google-id-token')

    expect(
      await screen.findByRole('heading', { name: 'Two-factor authentication' }),
    ).toBeInTheDocument()
    expect(router.state.location.state).toMatchObject({
      preAuthToken: 'pre-auth-google',
    })
    expect(tokenStorage.getAccess()).toBeNull()
  })

  it('shows why the backend rejected the Google account', async () => {
    server.use(
      http.post(api('/auth/social/google/'), () =>
        apiError(400, { non_field_errors: ['This account has been blocked.'] }),
      ),
    )
    const google = installFakeGoogle()
    renderApp('/login')
    await screen.findByRole('button', { name: 'Sign in with Google' })

    await google.pickAccount('google-id-token')

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'This account has been blocked.',
    )
    expect(tokenStorage.getAccess()).toBeNull()
  })

  it('hides Google sign-in when no client id is configured', async () => {
    vi.stubEnv('VITE_GOOGLE_CLIENT_ID', '')
    const google = installFakeGoogle()
    renderApp('/login')

    expect(
      await screen.findByRole('heading', { name: 'Log in' }),
    ).toBeInTheDocument()
    expect(
      screen.queryByRole('button', { name: 'Sign in with Google' }),
    ).not.toBeInTheDocument()
    expect(google.initialize).not.toHaveBeenCalled()
  })
})
