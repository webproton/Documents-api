import { screen } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import { api, server } from '@/test/server'
import { renderApp } from '@/test/utils'

const TOKEN = '6f9a1d2e-0000-4000-8000-000000000001'

describe('ConfirmEmailPage', () => {
  it('confirms the token from the link exactly once', async () => {
    const received: unknown[] = []
    server.use(
      http.post(api('/auth/confirm-email/'), async ({ request }) => {
        received.push(await request.json())
        return HttpResponse.json({ message: 'Email confirmed.' })
      }),
    )
    renderApp(`/confirm-email?token=${TOKEN}`)

    expect(await screen.findByRole('status')).toHaveTextContent(
      'Your email is confirmed',
    )
    expect(received).toEqual([{ token: TOKEN }])
  })

  it('reports an invalid or already used link', async () => {
    server.use(
      http.post(api('/auth/confirm-email/'), () =>
        HttpResponse.json(
          { error: 'Invalid or expired token' },
          { status: 400 },
        ),
      ),
    )
    renderApp(`/confirm-email?token=${TOKEN}`)

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'invalid, expired or has already been used',
    )
  })

  it('does not call the API without a token', async () => {
    // No handler: an API call would fail the test (onUnhandledRequest: 'error')
    renderApp('/confirm-email')

    expect(await screen.findByRole('alert')).toBeInTheDocument()
  })
})
