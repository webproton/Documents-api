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
}

/** Handlers every test gets; override per test with server.use(...). */
export const defaultHandlers = [
  http.get(api('/profile/'), () => HttpResponse.json(testProfile)),
]

export const server = setupServer(...defaultHandlers)

/** DRF error in the shape produced by the custom exception handler. */
export const apiError = (status: number, errors: unknown) =>
  HttpResponse.json({ status: 'error', errors }, { status })
