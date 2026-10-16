import { render } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import {
  createMemoryRouter,
  RouterProvider,
  type InitialEntry,
} from 'react-router'

import { AppProviders } from '@/AppProviders'
import { createQueryClient } from '@/lib/queryClient'
import { tokenStorage } from '@/lib/storage'
import { routes } from '@/routes/router'

type UserEventOptions = Parameters<typeof userEvent.setup>[0]

/**
 * Render the whole app (providers + real routes) at the given entry:
 * a URL string, or { pathname, state } to pass router state.
 */
export function renderApp(entry: InitialEntry, userOptions?: UserEventOptions) {
  const router = createMemoryRouter(routes, { initialEntries: [entry] })
  const user = userEvent.setup(userOptions)
  render(
    // No retries: a failed request shows its error right away
    <AppProviders queryClient={createQueryClient(0)}>
      <RouterProvider router={router} />
    </AppProviders>,
  )
  return { router, user }
}

/** Pretend the user is already logged in. */
export function signInAs(access = 'access-token', refresh = 'refresh-token') {
  tokenStorage.setTokens(access, refresh)
}
