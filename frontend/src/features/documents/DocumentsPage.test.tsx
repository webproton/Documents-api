import { screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { renderApp, signInAs } from '@/test/utils'

import {
  dayFromToday,
  mockDocumentsApi,
  storedDocument,
  VISA,
} from './documentsMock'

const pdf = (name = 'scan.pdf', size = 1024) =>
  new File([new Uint8Array(size)], name, { type: 'application/pdf' })

async function openDocuments(
  options?: Parameters<typeof mockDocumentsApi>[0],
  path = '/documents',
  userOptions?: Parameters<typeof renderApp>[1],
) {
  const mock = mockDocumentsApi(options)
  signInAs()
  const app = renderApp(path, userOptions)
  await screen.findByRole('heading', { name: 'My documents' })
  return { ...mock, ...app }
}

describe('DocumentsPage', () => {
  it('shows one card per folder with its active document', async () => {
    await openDocuments({
      documents: [
        storedDocument({ id: 1, name: 'Old passport', status: 'REPLACED' }),
        storedDocument({ id: 2, name: 'New passport' }),
        storedDocument({
          id: 3,
          name: 'Schengen visa',
          document_type: VISA.id,
          expiration_date: dayFromToday(10),
        }),
      ],
    })

    const cards = await screen.findAllByRole('listitem')
    expect(cards).toHaveLength(2)
    expect(within(cards[0]).getByText('New passport')).toBeInTheDocument()
    expect(within(cards[0]).queryByText('Old passport')).not.toBeInTheDocument()
    expect(
      within(cards[0]).getByRole('link', { name: 'Open folder' }),
    ).toHaveAttribute('href', '/documents/1')
    expect(
      within(cards[0]).getByRole('link', { name: 'Download' }),
    ).toHaveAttribute('href', expect.stringContaining('X-Amz-Signature'))
    // Expiring within 30 days is highlighted
    expect(within(cards[1]).getByText('In 10 days')).toBeInTheDocument()
  })

  it('marks expired documents', async () => {
    await openDocuments({
      documents: [storedDocument({ expiration_date: dayFromToday(-1) })],
    })

    expect(await screen.findByText('Expired')).toBeInTheDocument()
  })

  it('sends search, ordering and expiration filters', async () => {
    const { requests, user, router } = await openDocuments({
      documents: [storedDocument({})],
    })
    await screen.findAllByRole('listitem')

    await user.type(screen.getByRole('searchbox'), 'pass')
    await user.selectOptions(
      screen.getByLabelText('Sort by'),
      '-documents__created',
    )
    await user.type(screen.getByLabelText('Expires from'), '2027-01-01')

    await expect
      .poll(() => requests.at(-1)?.url)
      .toBe(
        '/folders/?search=pass&ordering=-documents__created&expiration_date_from=2027-01-01',
      )
    expect(router.state.location.search).toContain('expires_from=2027-01-01')
  })

  it('explains the empty states', async () => {
    await openDocuments()
    expect(
      await screen.findByText('No documents yet. Upload your first one.'),
    ).toBeInTheDocument()
  })

  describe('upload', () => {
    it('uploads a document and shows it in the list', async () => {
      const { requests, user } = await openDocuments()
      await user.click(screen.getByRole('button', { name: 'Upload document' }))
      const dialog = within(await screen.findByRole('dialog'))

      await user.selectOptions(
        await dialog.findByLabelText('Document type'),
        'Visa',
      )
      await user.upload(dialog.getByLabelText('File'), pdf('visa-scan.pdf'))
      // The file name is suggested as the document name
      expect(dialog.getByLabelText('Name')).toHaveValue('visa-scan')
      await user.type(dialog.getByLabelText('Expiration date'), '2028-05-01')
      await user.click(dialog.getByRole('button', { name: 'Upload' }))

      expect(
        await screen.findByText('“visa-scan” uploaded.'),
      ).toBeInTheDocument()
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
      expect(requests.find((r) => r.method === 'POST')?.body).toEqual({
        file: 'visa-scan.pdf',
        document_type: String(VISA.id),
        name: 'visa-scan',
        expiration_date: '2028-05-01',
      })
      expect(
        await screen.findByRole('heading', { name: 'visa-scan' }),
      ).toBeInTheDocument()
    })

    it('requires all fields', async () => {
      const { requests, user } = await openDocuments()
      await user.click(screen.getByRole('button', { name: 'Upload document' }))
      const dialog = within(await screen.findByRole('dialog'))

      await user.click(await dialog.findByRole('button', { name: 'Upload' }))

      expect(
        await dialog.findByText('Choose a document type'),
      ).toBeInTheDocument()
      expect(dialog.getByText('Choose a file')).toBeInTheDocument()
      expect(dialog.getByText('Enter a name')).toBeInTheDocument()
      expect(dialog.getByText('Choose an expiration date')).toBeInTheDocument()
      expect(requests.filter((r) => r.method === 'POST')).toEqual([])
    })

    it('rejects unsupported formats before uploading', async () => {
      const { user } = await openDocuments({}, '/documents', {
        applyAccept: false,
      })
      await user.click(screen.getByRole('button', { name: 'Upload document' }))
      const dialog = within(await screen.findByRole('dialog'))

      await user.upload(
        await dialog.findByLabelText('File'),
        new File(['x'], 'photo.png', { type: 'image/png' }),
      )
      await user.click(dialog.getByRole('button', { name: 'Upload' }))

      expect(
        await dialog.findByText(/Unsupported file format/),
      ).toBeInTheDocument()
    })

    it('offers a plan upgrade when the upload limit is reached', async () => {
      const { user } = await openDocuments({
        documents: [storedDocument({})],
        uploadLimit: 1,
      })
      await user.click(screen.getByRole('button', { name: 'Upload document' }))
      const dialog = within(await screen.findByRole('dialog'))

      await user.selectOptions(
        await dialog.findByLabelText('Document type'),
        'Visa',
      )
      await user.upload(dialog.getByLabelText('File'), pdf())
      await user.type(dialog.getByLabelText('Expiration date'), '2028-05-01')
      await user.click(dialog.getByRole('button', { name: 'Upload' }))

      expect(await dialog.findByRole('alert')).toHaveTextContent(
        'Document limit reached (1)',
      )
      expect(dialog.getByRole('link', { name: 'See plans' })).toHaveAttribute(
        'href',
        '/billing',
      )
    })

    it('closes with Escape', async () => {
      const { user } = await openDocuments()
      await user.click(screen.getByRole('button', { name: 'Upload document' }))
      await screen.findByRole('dialog')

      await user.keyboard('{Escape}')

      expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    })
  })
})
