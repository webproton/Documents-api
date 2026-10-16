import { act, screen } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { tokenStorage } from '@/lib/storage'
import { api, apiError, server } from '@/test/server'
import { renderApp } from '@/test/utils'

import type { TwoFactorState } from './two-factor'

const PRE_AUTH_TOKEN = '0b7e3c2a-1111-4000-8000-000000000001'

const twoFactorEntry = (state: Partial<TwoFactorState> = {}) => ({
  pathname: '/2fa',
  state: {
    preAuthToken: PRE_AUTH_TOKEN,
    deliveryMethod: 'EMAIL',
    message: 'Verification code has been sent to your email.',
    ...state,
  } satisfies TwoFactorState,
})

const verified = (extra: object = {}) =>
  HttpResponse.json({
    access: 'access-2fa',
    refresh: 'refresh-2fa',
    device_token: 'device-session',
    id: 1,
    email: 'user@example.com',
    ...extra,
  })

async function enterCode(
  user: ReturnType<typeof renderApp>['user'],
  code = '123456',
) {
  await user.type(await screen.findByLabelText('Verification code'), code)
  await user.click(screen.getByRole('button', { name: 'Verify' }))
}

describe('TwoFactorPage', () => {
  afterEach(() => {
    vi.useRealTimers()
  })

  it('redirects to login when opened without a 2FA session', async () => {
    const { router } = renderApp('/2fa')

    expect(
      await screen.findByRole('heading', { name: 'Log in' }),
    ).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/login')
  })

  it('shows where the code was sent', async () => {
    renderApp(twoFactorEntry())

    expect(
      await screen.findByText('Verification code has been sent to your email.'),
    ).toBeInTheDocument()
  })

  it('signs in and trusts the device by default', async () => {
    let body: unknown
    server.use(
      http.post(api('/auth/2fa/verify/'), async ({ request }) => {
        body = await request.json()
        return verified({ device_token: 'device-90d' })
      }),
    )
    const { router, user } = renderApp(twoFactorEntry())

    await enterCode(user)

    expect(
      await screen.findByRole('heading', { name: 'My documents' }),
    ).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/documents')
    expect(body).toEqual({
      pre_auth_token: PRE_AUTH_TOKEN,
      code: '123456',
      remember_device: true,
    })
    expect(tokenStorage.getAccess()).toBe('access-2fa')
    expect(tokenStorage.getDeviceToken()).toBe('device-90d')
  })

  it('does not ask to trust the device when unchecked', async () => {
    let body: { remember_device?: boolean } = {}
    server.use(
      http.post(api('/auth/2fa/verify/'), async ({ request }) => {
        body = (await request.json()) as typeof body
        return verified()
      }),
    )
    const { user } = renderApp(twoFactorEntry())

    await user.click(
      await screen.findByLabelText('Trust this device for 90 days'),
    )
    await enterCode(user)

    expect(
      await screen.findByRole('heading', { name: 'My documents' }),
    ).toBeInTheDocument()
    expect(body.remember_device).toBe(false)
    // The session token is stored either way; the backend just won't trust it
    expect(tokenStorage.getDeviceToken()).toBe('device-session')
  })

  it('returns to the page requested before login', async () => {
    server.use(http.post(api('/auth/2fa/verify/'), () => verified()))
    const { router, user } = renderApp(
      twoFactorEntry({
        from: {
          pathname: '/billing',
          search: '',
          hash: '',
          state: null,
          key: 'x',
        },
      }),
    )

    await enterCode(user)

    expect(
      await screen.findByRole('heading', { name: 'Plans & billing' }),
    ).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/billing')
  })

  it('keeps the form after a wrong code and shows attempts left', async () => {
    server.use(
      http.post(api('/auth/2fa/verify/'), () =>
        apiError(400, {
          non_field_errors: [
            'Invalid verification code. 2 attempt(s) remaining.',
          ],
        }),
      ),
    )
    const { user } = renderApp(twoFactorEntry())

    await enterCode(user)

    expect(await screen.findByRole('alert')).toHaveTextContent(
      '2 attempt(s) remaining',
    )
    // Code field is cleared for the next attempt
    expect(screen.getByLabelText('Verification code')).toHaveValue('')
    expect(screen.getByRole('button', { name: 'Verify' })).toBeEnabled()
  })

  it.each([
    'Maximum 2FA verification attempts exceeded. Please log in again.',
    'Invalid or expired 2FA session. Please log in again.',
  ])('ends the 2FA session: %s', async (message) => {
    server.use(
      http.post(api('/auth/2fa/verify/'), () =>
        apiError(400, { non_field_errors: [message] }),
      ),
    )
    const { user } = renderApp(twoFactorEntry())

    await enterCode(user)

    expect(await screen.findByRole('alert')).toHaveTextContent(message)
    expect(screen.queryByLabelText('Verification code')).not.toBeInTheDocument()
    expect(
      screen.getByRole('link', { name: 'Back to log in' }),
    ).toHaveAttribute('href', '/login')
    expect(tokenStorage.getAccess()).toBeNull()
  })

  it('validates the code format before calling the API', async () => {
    // No verify handler: an API call would fail the test
    const { user } = renderApp(twoFactorEntry())

    await enterCode(user, '12ab')

    expect(
      await screen.findByText('Enter the 6-digit code'),
    ).toBeInTheDocument()
  })

  it('allows resending the code only after the cooldown', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    let resendBody: unknown
    server.use(
      http.post(api('/auth/2fa/resend/'), async ({ request }) => {
        resendBody = await request.json()
        return HttpResponse.json({
          message: 'A new verification code has been sent to your email.',
        })
      }),
    )
    const { user } = renderApp(twoFactorEntry(), {
      advanceTimers: vi.advanceTimersByTime,
    })

    expect(
      await screen.findByRole('button', { name: /Resend code in 60s/ }),
    ).toBeDisabled()

    await act(() => vi.advanceTimersByTimeAsync(60_000))
    await user.click(screen.getByRole('button', { name: 'Resend code' }))

    expect(
      await screen.findByText(
        'A new verification code has been sent to your email.',
      ),
    ).toBeInTheDocument()
    expect(resendBody).toEqual({ pre_auth_token: PRE_AUTH_TOKEN })
    // Cooldown starts again after a successful resend
    expect(
      screen.getByRole('button', { name: /Resend code in \d+s/ }),
    ).toBeDisabled()
  })
})
