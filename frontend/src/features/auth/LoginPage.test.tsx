import { screen } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import { tokenStorage } from '@/lib/storage'
import { api, apiError, server } from '@/test/server'
import { renderApp } from '@/test/utils'

async function submitLogin(
  user: ReturnType<typeof renderApp>['user'],
  email = 'user@example.com',
  password = 'StrongPass123',
) {
  await user.type(await screen.findByLabelText('Email'), email)
  await user.type(screen.getByLabelText('Password'), password)
  await user.click(screen.getByRole('button', { name: 'Log in' }))
}

describe('LoginPage', () => {
  it('stores tokens and opens the app when 2FA is not required', async () => {
    server.use(
      http.post(api('/auth/login/'), () =>
        HttpResponse.json({
          access: 'new-access',
          refresh: 'new-refresh',
          id: 1,
          email: 'user@example.com',
          requires_2fa: false,
        }),
      ),
    )
    const { router, user } = renderApp('/login')

    await submitLogin(user)

    expect(
      await screen.findByRole('heading', { name: 'My documents' }),
    ).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/documents')
    expect(tokenStorage.getAccess()).toBe('new-access')
    expect(tokenStorage.getRefresh()).toBe('new-refresh')
  })

  it('goes to the 2FA step when the backend answers 202', async () => {
    server.use(
      http.post(api('/auth/login/'), () =>
        HttpResponse.json(
          {
            requires_2fa: true,
            pre_auth_token: '3f1c…',
            delivery_method: 'EMAIL',
            message: 'Verification code has been sent to your email.',
          },
          { status: 202 },
        ),
      ),
    )
    const { router, user } = renderApp('/login')

    await submitLogin(user)

    expect(
      await screen.findByRole('heading', { name: 'Two-factor authentication' }),
    ).toBeInTheDocument()
    expect(router.state.location.state).toEqual({
      preAuthToken: '3f1c…',
      deliveryMethod: 'EMAIL',
      message: 'Verification code has been sent to your email.',
    })
    expect(tokenStorage.getAccess()).toBeNull()
  })

  it('shows the backend message for wrong credentials', async () => {
    server.use(
      http.post(api('/auth/login/'), () =>
        apiError(401, {
          detail: 'No active account found with the given credentials',
        }),
      ),
    )
    const { user } = renderApp('/login')

    await submitLogin(user)

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'No active account found with the given credentials',
    )
    expect(tokenStorage.getAccess()).toBeNull()
  })

  it('validates the form before calling the API', async () => {
    const { user } = renderApp('/login')

    await user.click(await screen.findByRole('button', { name: 'Log in' }))

    expect(
      await screen.findByText('Enter a valid email address'),
    ).toBeInTheDocument()
    expect(screen.getByText('Enter your password')).toBeInTheDocument()
  })

  it('returns to the originally requested page after login', async () => {
    server.use(
      http.post(api('/auth/login/'), () =>
        HttpResponse.json({
          access: 'a',
          refresh: 'r',
          id: 1,
          email: 'user@example.com',
          requires_2fa: false,
        }),
      ),
    )
    const { router, user } = renderApp('/billing')

    // Guest is redirected to login first
    expect(
      await screen.findByRole('heading', { name: 'Log in' }),
    ).toBeInTheDocument()
    await submitLogin(user)

    expect(
      await screen.findByRole('heading', { name: 'Plans & billing' }),
    ).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/billing')
  })
})
