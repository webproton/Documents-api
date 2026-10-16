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

describe('app shell', () => {
  it('collapses the navigation behind a menu button on small screens', async () => {
    signInAs()
    const { user } = renderApp('/documents')
    const menuButton = await screen.findByRole('button', { name: 'Menu' })

    expect(menuButton).toHaveAttribute('aria-expanded', 'false')
    expect(screen.getByRole('navigation')).toHaveClass('hidden', 'lg:flex')

    await user.click(menuButton)
    expect(menuButton).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByRole('navigation')).not.toHaveClass('hidden')

    // Choosing a page closes the menu
    await user.click(
      within(screen.getByRole('navigation')).getByRole('link', {
        name: 'Billing',
      }),
    )
    expect(menuButton).toHaveAttribute('aria-expanded', 'false')
  })

  it('sets the browser tab title for each page', async () => {
    signInAs()
    renderApp('/types')

    await screen.findByRole('heading', { name: 'Document types' })
    expect(document.title).toBe('Document types · Documents')
  })
})
