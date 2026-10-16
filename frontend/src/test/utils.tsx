import { render } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createMemoryRouter, RouterProvider } from 'react-router'

import { AppProviders } from '@/AppProviders'
import { tokenStorage } from '@/lib/storage'
import { routes } from '@/routes/router'

/** Render the whole app (providers + real routes) at the given URL. */
export function renderApp(path: string) {
  const router = createMemoryRouter(routes, { initialEntries: [path] })
  const user = userEvent.setup()
  render(
    <AppProviders>
      <RouterProvider router={router} />
    </AppProviders>,
  )
  return { router, user }
}

/** Pretend the user is already logged in. */
export function signInAs(access = 'access-token', refresh = 'refresh-token') {
  tokenStorage.setTokens(access, refresh)
}
