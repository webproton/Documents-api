import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'

import type { Profile } from '@/api/profile'

/** Same base URL the app uses (jsdom origin + VITE_API_URL default). */
export const api = (path: string) => `/api${path}`

export const testProfile: Profile = {
  id: 1,
  email: 'user@example.com',
  first_name: 'Test',
  last_name: 'User',
  avatar: null,
  is_2fa_enabled: false,
  two_factor_method: 'EMAIL',
  phone_number: null,
  phone_confirmed: false,
  has_password: true,
}

/**
 * Handlers every test gets: a signed-in user with an empty account.
 * Pages reached as a side effect (e.g. /documents after login) load
 * without errors; tests that need data override with server.use(...).
 */
export const defaultHandlers = [
  http.get(api('/profile/'), () => HttpResponse.json(testProfile)),
  http.get(api('/documents/folders/'), () => HttpResponse.json([])),
  http.get(api('/documents/types/'), () => HttpResponse.json([])),
  http.get(api('/billing/plans/'), () => HttpResponse.json([])),
  // No subscription yet
  http.get(api('/billing/subscription/'), () =>
    HttpResponse.json(null, { status: 404 }),
  ),
  // Unknown upload link
  http.get(api('/documents/upload/:token/'), () =>
    HttpResponse.json(
      { status: 'error', errors: { detail: 'Not found.' } },
      { status: 404 },
    ),
  ),
]

export const server = setupServer(...defaultHandlers)

/** DRF error in the shape produced by the custom exception handler. */
export const apiError = (status: number, errors: unknown) =>
  HttpResponse.json({ status: 'error', errors }, { status })
