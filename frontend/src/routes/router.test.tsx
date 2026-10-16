import { screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { renderApp, signInAs } from '@/test/utils'

describe('router', () => {
  it('redirects home to documents inside the main layout', async () => {
    signInAs()
    const { router } = renderApp('/')

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
    renderApp('/login')

    expect(
      await screen.findByRole('heading', { name: 'Log in' }),
    ).toBeInTheDocument()
    expect(screen.queryByRole('navigation')).not.toBeInTheDocument()
  })

  it.each(['/upload/abc', '/billing/success', '/billing/cancel'])(
    'serves %s linked from backend emails and Stripe',
    async (path) => {
      signInAs()
      renderApp(path)

      expect(await screen.findByRole('heading')).toBeInTheDocument()
      expect(screen.queryByText('Page not found')).not.toBeInTheDocument()
    },
  )

  it('shows 404 for unknown paths', async () => {
    renderApp('/no-such-page')

    expect(await screen.findByText('Page not found')).toBeInTheDocument()
  })
})
