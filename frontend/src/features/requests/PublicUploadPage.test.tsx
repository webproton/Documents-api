import { screen } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import type { UploadLinkDetails } from '@/api/requests'
import { PASSPORT } from '@/features/documents/documentsMock'
import { tokenStorage } from '@/lib/storage'
import { api, apiError, server } from '@/test/server'
import { renderApp } from '@/test/utils'

const TOKEN = '9b2c5c3e-0000-4000-8000-000000000001'

const details = (
  overrides: Partial<UploadLinkDetails> = {},
): UploadLinkDetails => ({
  document_type: {
    ...PASSPORT,
    description: 'Scan of the photo page',
    template: 'https://bucket.s3.amazonaws.com/templates/passport.pdf?sig=x',
  },
  requester_email: 'owner@example.com',
  status: 'PENDING',
  expires_at: '2026-11-15T10:00:00Z',
  ...overrides,
})

function mockLink(linkDetails: UploadLinkDetails | 404) {
  const uploads: string[] = []
  server.use(
    http.get(api(`/documents/upload/${TOKEN}/`), () =>
      linkDetails === 404
        ? apiError(404, {
            detail: 'No DocumentRequest matches the given query.',
          })
        : HttpResponse.json(linkDetails),
    ),
    http.post(api(`/documents/upload/${TOKEN}/`), async ({ request }) => {
      uploads.push(await request.text())
      return HttpResponse.json({ id: 1 }, { status: 201 })
    }),
  )
  return { uploads }
}

describe('PublicUploadPage', () => {
  it('shows what is requested and by whom, without logging in', async () => {
    mockLink(details())
    renderApp(`/upload/${TOKEN}`)

    expect(
      await screen.findByRole('heading', { name: 'Upload: Passport' }),
    ).toBeInTheDocument()
    expect(screen.getByText('owner@example.com')).toBeInTheDocument()
    expect(screen.getByText('Scan of the photo page')).toBeInTheDocument()
    expect(
      screen.getByRole('link', { name: 'Download the template' }),
    ).toHaveAttribute('href', expect.stringContaining('passport.pdf'))
    expect(tokenStorage.getAccess()).toBeNull()
  })

  it('uploads one document and thanks the recipient', async () => {
    const { uploads } = mockLink(details())
    const { user } = renderApp(`/upload/${TOKEN}`)

    await user.upload(
      await screen.findByLabelText('File'),
      new File(['%PDF'], 'my-passport.pdf', { type: 'application/pdf' }),
    )
    await user.type(
      screen.getByLabelText('Expiration date (optional)'),
      '2030-01-01',
    )
    await user.click(screen.getByRole('button', { name: 'Upload document' }))

    expect(await screen.findByText(/Thank you!/)).toBeInTheDocument()
    expect(screen.queryByLabelText('File')).not.toBeInTheDocument()
    expect(uploads).toHaveLength(1)
    expect(uploads[0]).toContain('filename="my-passport.pdf"')
    expect(uploads[0]).toContain('2030-01-01')
    // Empty optional name is not sent
    expect(uploads[0]).not.toContain('name="name"')
  })

  it('requires a supported file', async () => {
    const { uploads } = mockLink(details())
    const { user } = renderApp(`/upload/${TOKEN}`)

    await user.click(
      await screen.findByRole('button', { name: 'Upload document' }),
    )

    expect(await screen.findByText('Choose a file')).toBeInTheDocument()
    expect(uploads).toEqual([])
  })

  it.each([
    ['COMPLETED', /already been uploaded/],
    ['CANCELED', /canceled by the person who sent it/],
    ['EXPIRED', /link has expired/],
  ] as const)(
    'explains a %s link instead of the form',
    async (status, text) => {
      mockLink(details({ status }))
      renderApp(`/upload/${TOKEN}`)

      expect(await screen.findByText(text)).toBeInTheDocument()
      expect(screen.queryByLabelText('File')).not.toBeInTheDocument()
    },
  )

  it('reports an unknown link', async () => {
    mockLink(404)
    renderApp(`/upload/${TOKEN}`)

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'This upload link is not valid',
    )
  })

  it('shows an upload error from the backend', async () => {
    mockLink(details())
    server.use(
      http.post(api(`/documents/upload/${TOKEN}/`), () =>
        apiError(400, { token: ['This secure upload link has expired.'] }),
      ),
    )
    const { user } = renderApp(`/upload/${TOKEN}`)

    await user.upload(
      await screen.findByLabelText('File'),
      new File(['%PDF'], 'a.pdf', { type: 'application/pdf' }),
    )
    await user.click(screen.getByRole('button', { name: 'Upload document' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'This secure upload link has expired.',
    )
  })
})
