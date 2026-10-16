import { screen } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import { tokenStorage } from '@/lib/storage'
import { api, apiError, server } from '@/test/server'
import { renderApp, signInAs } from '@/test/utils'

describe('session', () => {
  it('sends a guest from a protected page to login', async () => {
    const { router } = renderApp('/profile')

    expect(
      await screen.findByRole('heading', { name: 'Log in' }),
    ).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/login')
  })

  it('sends a signed-in user away from login', async () => {
    signInAs()
    const { router } = renderApp('/login')

    expect(
      await screen.findByRole('heading', { name: 'My documents' }),
    ).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/documents')
  })

  it('shows the current user in the header', async () => {
    signInAs()
    renderApp('/documents')

    expect(await screen.findByText('user@example.com')).toBeInTheDocument()
  })

  it('logs out: blacklists refresh, keeps the trusted device', async () => {
    let logoutBody: unknown
    server.use(
      http.post(api('/auth/logout/'), async ({ request }) => {
        logoutBody = await request.json()
        return HttpResponse.json({ message: 'Logged out successfully' })
      }),
    )
    signInAs('access-1', 'refresh-1')
    tokenStorage.setDeviceToken('device-1')
    const { user, router } = renderApp('/documents')

    await user.click(await screen.findByRole('button', { name: 'Log out' }))

    expect(
      await screen.findByRole('heading', { name: 'Log in' }),
    ).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/login')
    expect(logoutBody).toEqual({ refresh: 'refresh-1' })
    expect(tokenStorage.getAccess()).toBeNull()
    expect(tokenStorage.getRefresh()).toBeNull()
    expect(tokenStorage.getDeviceToken()).toBe('device-1')
  })

  it('logs out locally even if the server call fails', async () => {
    server.use(
      http.post(api('/auth/logout/'), () =>
        apiError(400, { detail: 'Token is blacklisted' }),
      ),
    )
    signInAs()
    const { user } = renderApp('/documents')

    await user.click(await screen.findByRole('button', { name: 'Log out' }))

    expect(
      await screen.findByRole('heading', { name: 'Log in' }),
    ).toBeInTheDocument()
    expect(tokenStorage.getAccess()).toBeNull()
  })

  it('ends the session when the refresh token is rejected', async () => {
    server.use(
      http.get(api('/profile/'), () =>
        apiError(401, { detail: 'Given token not valid for any token type' }),
      ),
      http.post(api('/auth/refresh/'), () =>
        apiError(401, { detail: 'Token is blacklisted' }),
      ),
    )
    signInAs()
    const { router } = renderApp('/documents')

    expect(
      await screen.findByRole('heading', { name: 'Log in' }),
    ).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/login')
    expect(tokenStorage.getRefresh()).toBeNull()
    // The user is told why they are back on the login page
    expect(
      screen.getByText('Your session has ended. Please log in again.'),
    ).toBeInTheDocument()
  })

  it('does not say the session ended after a normal logout', async () => {
    // Logout with an already expired access token: refresh fails too
    server.use(
      http.post(api('/auth/logout/'), () =>
        apiError(401, { detail: 'Token is invalid or expired' }),
      ),
      http.post(api('/auth/refresh/'), () =>
        apiError(401, { detail: 'Token is blacklisted' }),
      ),
    )
    signInAs()
    const { user } = renderApp('/documents')

    await user.click(await screen.findByRole('button', { name: 'Log out' }))

    expect(
      await screen.findByRole('heading', { name: 'Log in' }),
    ).toBeInTheDocument()
    expect(
      screen.queryByText('Your session has ended. Please log in again.'),
    ).not.toBeInTheDocument()
  })
})
