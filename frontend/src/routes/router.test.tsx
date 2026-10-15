import { render, screen, within } from '@testing-library/react'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { describe, expect, it } from 'vitest'

import { AppProviders } from '@/AppProviders'

import { routes } from './router'

function renderAt(path: string) {
  const router = createMemoryRouter(routes, { initialEntries: [path] })
  render(
    <AppProviders>
      <RouterProvider router={router} />
    </AppProviders>,
  )
  return router
}

describe('router', () => {
  it('redirects home to documents inside the main layout', async () => {
    const router = renderAt('/')

    expect(
      await screen.findByRole('heading', { name: 'My documents' }),
    ).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/documents')
    const nav = screen.getByRole('navigation')
    expect(
      within(nav).getByRole('link', { name: 'Documents' }),
    ).toHaveAttribute('aria-current', 'page')
  })

  it('renders guest pages without the main navigation', async () => {
    renderAt('/login')

    expect(
      await screen.findByRole('heading', { name: 'Log in' }),
    ).toBeInTheDocument()
    expect(screen.queryByRole('navigation')).not.toBeInTheDocument()
  })

  it.each([
    '/confirm-email',
    '/upload/abc',
    '/billing/success',
    '/billing/cancel',
  ])('serves %s linked from backend emails and Stripe', async (path) => {
    renderAt(path)

    expect(await screen.findByRole('heading')).toBeInTheDocument()
    expect(screen.queryByText('Page not found')).not.toBeInTheDocument()
  })

  it('shows 404 for unknown paths', async () => {
    renderAt('/no-such-page')

    expect(await screen.findByText('Page not found')).toBeInTheDocument()
  })
})
