import { screen, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import type { Profile } from '@/api/profile'
import type { UserDevice } from '@/api/security'
import { api, apiError, server, testProfile } from '@/test/server'
import { renderApp, signInAs } from '@/test/utils'

const CHROME_MAC =
  'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/118.0.0.0 Safari/537.36'
const SAFARI_IPHONE =
  'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Version/17.0 Mobile/15E148 Safari/604.1'

const device = (overrides: Partial<UserDevice>): UserDevice => ({
  id: 1,
  user_agent: CHROME_MAC,
  ip_address: '93.175.10.1',
  location: 'Kyiv, Ukraine',
  last_login_at: '2026-10-16T09:00:00Z',
  is_current: false,
  is_active_session: true,
  is_trusted: false,
  trusted_until: null,
  ...overrides,
})

/** In-memory backend for profile, 2FA, phone and devices endpoints. */
function mockSecurityApi({
  profile: profileOverrides = {},
  devices: initialDevices = [],
}: { profile?: Partial<Profile>; devices?: UserDevice[] } = {}) {
  const profile: Profile = { ...testProfile, ...profileOverrides }
  let devices = [...initialDevices]
  const calls: { url: string; body?: unknown }[] = []
  const record = async (request: Request) => {
    const text = await request.text()
    calls.push({
      url: new URL(request.url).pathname,
      body: text ? JSON.parse(text) : undefined,
    })
  }

  server.use(
    http.get(api('/profile/'), () => HttpResponse.json(profile)),
    http.post(api('/profile/2fa/toggle/'), async ({ request }) => {
      await record(request.clone())
      const body = (await request.json()) as {
        enable: boolean
        method: Profile['two_factor_method']
      }
      profile.is_2fa_enabled = body.enable
      if (body.enable) profile.two_factor_method = body.method
      return HttpResponse.json({ message: '2FA updated.' })
    }),
    http.post(
      api('/profile/phone/request-confirmation/'),
      async ({ request }) => {
        await record(request)
        return HttpResponse.json({ message: 'Confirmation code sent.' })
      },
    ),
    http.post(api('/profile/phone/confirm/'), async ({ request }) => {
      await record(request)
      profile.phone_number = '+380501234567'
      profile.phone_confirmed = true
      return HttpResponse.json({ message: 'Phone number confirmed.' })
    }),
    http.get(api('/devices/'), () => HttpResponse.json(devices)),
    http.post(api('/devices/:id/revoke/'), async ({ request, params }) => {
      await record(request)
      devices = devices.filter((d) => d.id !== Number(params.id))
      return HttpResponse.json({ message: 'Device revoked successfully.' })
    }),
    http.post(api('/devices/revoke-all/'), async ({ request }) => {
      await record(request)
      const revoked = devices.filter((d) => !d.is_current).length
      devices = devices.filter((d) => d.is_current)
      return HttpResponse.json({
        message: `Revoked ${revoked} device(s) successfully.`,
      })
    }),
  )
  return { calls }
}

async function openSecurity(options?: Parameters<typeof mockSecurityApi>[0]) {
  const mock = mockSecurityApi(options)
  signInAs()
  const app = renderApp('/security')
  await screen.findByRole('heading', { name: 'Two-factor authentication' })
  return { ...mock, ...app }
}

const card = (title: string) =>
  within(
    screen
      .getByRole('heading', { name: title })
      .closest('section') as HTMLElement,
  )

describe('SecurityPage', () => {
  describe('two-factor authentication', () => {
    it('turns 2FA on by email with the password', async () => {
      const { calls, user } = await openSecurity()
      const twoFactor = card('Two-factor authentication')
      expect(twoFactor.getByText('Off')).toBeInTheDocument()

      await user.type(twoFactor.getByLabelText('Password'), 'MyPass123')
      await user.click(twoFactor.getByRole('button', { name: 'Turn on 2FA' }))

      expect(
        await twoFactor.findByText('On · codes are sent by Email'),
      ).toBeInTheDocument()
      expect(calls).toEqual([
        {
          url: '/api/profile/2fa/toggle/',
          body: { enable: true, password: 'MyPass123', method: 'EMAIL' },
        },
      ])
      expect(
        twoFactor.getByRole('button', { name: 'Turn off 2FA' }),
      ).toBeInTheDocument()
    })

    it('turns 2FA off', async () => {
      const { calls, user } = await openSecurity({
        profile: { is_2fa_enabled: true },
      })
      const twoFactor = card('Two-factor authentication')

      await user.type(twoFactor.getByLabelText('Password'), 'MyPass123')
      await user.click(twoFactor.getByRole('button', { name: 'Turn off 2FA' }))

      expect(await twoFactor.findByText('Off')).toBeInTheDocument()
      expect(calls[0].body).toMatchObject({ enable: false })
    })

    it('allows SMS only with a confirmed phone', async () => {
      await openSecurity()

      expect(screen.getByRole('radio', { name: /SMS/ })).toBeDisabled()
      expect(
        screen.getByText(/confirm a phone number below first/),
      ).toBeInTheDocument()
    })

    it('enables SMS 2FA with a confirmed phone', async () => {
      const { calls, user } = await openSecurity({
        profile: { phone_number: '+380501234567', phone_confirmed: true },
      })
      const twoFactor = card('Two-factor authentication')

      await user.click(twoFactor.getByRole('radio', { name: /SMS/ }))
      await user.type(twoFactor.getByLabelText('Password'), 'MyPass123')
      await user.click(twoFactor.getByRole('button', { name: 'Turn on 2FA' }))

      expect(
        await twoFactor.findByText('On · codes are sent by SMS'),
      ).toBeInTheDocument()
      expect(calls[0].body).toMatchObject({ enable: true, method: 'SMS' })
    })

    it('shows a wrong password under the field', async () => {
      mockSecurityApi()
      server.use(
        http.post(api('/profile/2fa/toggle/'), () =>
          apiError(400, { password: ['Incorrect password.'] }),
        ),
      )
      signInAs()
      const { user } = renderApp('/security')
      const passwordInput = await screen.findByLabelText('Password')

      await user.type(passwordInput, 'wrong')
      await user.click(screen.getByRole('button', { name: 'Turn on 2FA' }))

      expect(await screen.findByText('Incorrect password.')).toBeInTheDocument()
    })

    it('asks Google-only users to set a password first', async () => {
      await openSecurity({ profile: { has_password: false } })
      const twoFactor = card('Two-factor authentication')

      expect(
        twoFactor.getByRole('link', { name: 'Set a password' }),
      ).toHaveAttribute('href', '/profile')
      expect(twoFactor.queryByLabelText('Password')).not.toBeInTheDocument()
    })
  })

  describe('phone number', () => {
    it('confirms a phone number with the SMS code', async () => {
      const { calls, user } = await openSecurity()
      const phone = card('Phone number')

      await user.type(phone.getByLabelText('Phone number'), '+380501234567')
      await user.click(phone.getByRole('button', { name: 'Send code' }))
      await user.type(await phone.findByLabelText('SMS code'), '654321')
      await user.click(phone.getByRole('button', { name: 'Confirm' }))

      expect(
        await phone.findByText('Phone number confirmed.'),
      ).toBeInTheDocument()
      expect(phone.getByText('+380501234567')).toBeInTheDocument()
      expect(calls).toEqual([
        {
          url: '/api/profile/phone/request-confirmation/',
          body: { phone_number: '+380501234567' },
        },
        { url: '/api/profile/phone/confirm/', body: { code: '654321' } },
      ])
      // SMS 2FA becomes available
      expect(screen.getByRole('radio', { name: /SMS/ })).toBeEnabled()
    })

    it('checks the phone format before sending', async () => {
      const { calls, user } = await openSecurity()
      const phone = card('Phone number')

      await user.type(phone.getByLabelText('Phone number'), '0501234567')
      await user.click(phone.getByRole('button', { name: 'Send code' }))

      expect(
        await phone.findByText('Use international format, e.g. +380501234567'),
      ).toBeInTheDocument()
      expect(calls).toEqual([])
    })

    it('shows a wrong SMS code', async () => {
      mockSecurityApi()
      server.use(
        http.post(api('/profile/phone/confirm/'), () =>
          apiError(400, { non_field_errors: ['Invalid or expired code.'] }),
        ),
      )
      signInAs()
      const { user } = renderApp('/security')
      const phoneInput = await screen.findByLabelText('Phone number')

      await user.type(phoneInput, '+380501234567')
      await user.click(screen.getByRole('button', { name: 'Send code' }))
      await user.type(await screen.findByLabelText('SMS code'), '000000')
      await user.click(screen.getByRole('button', { name: 'Confirm' }))

      expect(await screen.findByRole('alert')).toHaveTextContent(
        'Invalid or expired code.',
      )
    })
  })

  describe('devices and sessions', () => {
    const devices = [
      device({
        id: 1,
        is_current: true,
        is_trusted: true,
        trusted_until: '2027-01-14T09:00:00Z',
      }),
      device({ id: 2, user_agent: SAFARI_IPHONE, location: 'Lviv, Ukraine' }),
      device({
        id: 3,
        is_active_session: false,
        is_trusted: true,
        trusted_until: '2026-12-01T09:00:00Z',
      }),
    ]

    it('lists devices with browser, location, IP and status', async () => {
      await openSecurity({ devices })
      const sessions = card('Devices and sessions')

      const items = await sessions.findAllByRole('listitem')
      expect(items).toHaveLength(3)
      expect(within(items[0]).getByText('Chrome on macOS')).toBeInTheDocument()
      expect(within(items[0]).getByText('This device')).toBeInTheDocument()
      expect(within(items[0]).getByText(/Trusted until/)).toBeInTheDocument()
      expect(within(items[1]).getByText('Safari on iOS')).toBeInTheDocument()
      expect(
        within(items[1]).getByText(/Lviv, Ukraine · 93\.175\.10\.1/),
      ).toBeInTheDocument()
      expect(within(items[2]).getByText('Signed out')).toBeInTheDocument()
      // The current session is ended with "Log out", not from this list
      expect(
        within(items[0]).queryByRole('button', { name: 'End session' }),
      ).not.toBeInTheDocument()
    })

    it('ends a session on another device', async () => {
      const { calls, user } = await openSecurity({ devices })
      const sessions = card('Devices and sessions')
      const items = await sessions.findAllByRole('listitem')

      await user.click(
        within(items[1]).getByRole('button', { name: 'End session' }),
      )

      await expect
        .poll(() => sessions.queryAllByRole('listitem').length)
        .toBe(2)
      expect(calls).toEqual([
        { url: '/api/devices/2/revoke/', body: undefined },
      ])
      expect(sessions.queryByText('Safari on iOS')).not.toBeInTheDocument()
    })

    it('ends all other sessions', async () => {
      const { calls, user } = await openSecurity({ devices })
      const sessions = card('Devices and sessions')
      await sessions.findAllByRole('listitem')

      await user.click(
        sessions.getByRole('button', { name: 'End all other sessions' }),
      )

      expect(
        await sessions.findByText('Revoked 2 device(s) successfully.'),
      ).toBeInTheDocument()
      expect(calls).toEqual([
        { url: '/api/devices/revoke-all/', body: undefined },
      ])
      expect(sessions.getAllByRole('listitem')).toHaveLength(1)
      expect(
        sessions.queryByRole('button', { name: 'End all other sessions' }),
      ).not.toBeInTheDocument()
    })
  })
})
