import { screen, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import type { DocumentType } from '@/api/documents'
import { api, apiError, server } from '@/test/server'
import { renderApp, signInAs } from '@/test/utils'

const TYPES: DocumentType[] = [
  {
    id: 1,
    name: 'Passport',
    description: 'Identity document',
    template: 'https://bucket.s3.amazonaws.com/document_templates/passport.pdf',
  },
  { id: 2, name: 'Visa', description: 'Travel visa', template: null },
]

/** Search the way DRF SearchFilter does: name or description, case-insensitive. */
function mockTypesApi(types = TYPES) {
  const searches: (string | null)[] = []
  server.use(
    http.get(api('/documents/types/'), ({ request }) => {
      const search = new URL(request.url).searchParams.get('search')
      searches.push(search)
      const term = search?.toLowerCase() ?? ''
      return HttpResponse.json(
        types.filter((type) =>
          `${type.name} ${type.description}`.toLowerCase().includes(term),
        ),
      )
    }),
  )
  return { searches }
}

describe('DocumentTypesPage', () => {
  it('lists document types with descriptions and templates', async () => {
    mockTypesApi()
    signInAs()
    renderApp('/types')

    const cards = await screen.findAllByRole('listitem')
    expect(cards).toHaveLength(2)
    expect(within(cards[0]).getByText('Identity document')).toBeInTheDocument()
    expect(
      within(cards[0]).getByRole('link', { name: 'Download template' }),
    ).toHaveAttribute(
      'href',
      'https://bucket.s3.amazonaws.com/document_templates/passport.pdf',
    )
    // No template → no link
    expect(
      within(cards[1]).queryByRole('link', { name: 'Download template' }),
    ).not.toBeInTheDocument()
  })

  it('searches by name or description and keeps the query in the URL', async () => {
    const { searches } = mockTypesApi()
    signInAs()
    const { user, router } = renderApp('/types')
    await screen.findAllByRole('listitem')

    await user.type(
      screen.getByRole('searchbox', { name: 'Search document types' }),
      'travel',
    )

    await expect.poll(() => screen.queryAllByRole('listitem').length).toBe(1)
    expect(screen.getByText('Visa')).toBeInTheDocument()
    expect(router.state.location.search).toBe('?search=travel')
    // Debounced: one request for the whole word, not one per letter
    expect(searches).toEqual([null, 'travel'])
  })

  it('restores the search from the URL', async () => {
    const { searches } = mockTypesApi()
    signInAs()
    renderApp('/types?search=passport')

    expect(await screen.findByText('Passport')).toBeInTheDocument()
    expect(
      screen.getByRole('searchbox', { name: 'Search document types' }),
    ).toHaveValue('passport')
    expect(searches).toEqual(['passport'])
  })

  it('explains an empty search result', async () => {
    mockTypesApi()
    signInAs()
    renderApp('/types?search=nothing')

    expect(
      await screen.findByText('No document types match “nothing”.'),
    ).toBeInTheDocument()
  })

  it('explains that types are added by an administrator', async () => {
    mockTypesApi([])
    signInAs()
    renderApp('/types')

    expect(
      await screen.findByText(/They are added by an administrator/),
    ).toBeInTheDocument()
  })

  it('shows an API error', async () => {
    server.use(
      http.get(api('/documents/types/'), () =>
        apiError(500, { detail: 'Server error' }),
      ),
    )
    signInAs()
    renderApp('/types')

    expect(await screen.findByRole('alert')).toHaveTextContent('Server error')
  })
})
