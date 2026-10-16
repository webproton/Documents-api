import { screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { renderApp, signInAs } from '@/test/utils'

import { mockDocumentsApi, PASSPORT, storedDocument } from './documentsMock'

const versions = () => [
  storedDocument({
    id: 1,
    name: 'Passport 2020',
    status: 'REPLACED',
    created: '2020-03-01T10:00:00Z',
  }),
  storedDocument({
    id: 2,
    name: 'Passport 2025',
    created: '2025-06-01T10:00:00Z',
  }),
]

async function openFolder(options?: Parameters<typeof mockDocumentsApi>[0]) {
  const mock = mockDocumentsApi({ documents: versions(), ...options })
  signInAs()
  const app = renderApp(`/documents/${PASSPORT.id}`)
  await screen.findByRole('heading', { name: 'Passport' })
  return { ...mock, ...app }
}

const versionItem = (name: string) =>
  within(screen.getByText(name).closest('li') as HTMLElement)

describe('FolderPage', () => {
  it('lists all versions, newest first, with their status', async () => {
    await openFolder()

    const items = screen.getAllByRole('listitem')
    expect(within(items[0]).getByText('Passport 2025')).toBeInTheDocument()
    expect(within(items[0]).getByText('Active')).toBeInTheDocument()
    expect(within(items[1]).getByText('Passport 2020')).toBeInTheDocument()
    expect(within(items[1]).getByText('Replaced')).toBeInTheDocument()
  })

  it('edits the name and expiration date', async () => {
    const { requests, user } = await openFolder()
    const item = versionItem('Passport 2025')

    await user.click(item.getByRole('button', { name: 'Edit' }))
    await user.clear(item.getByLabelText('Name'))
    await user.type(item.getByLabelText('Name'), 'Main passport')
    await user.clear(item.getByLabelText('Expiration date'))
    await user.type(item.getByLabelText('Expiration date'), '2035-06-01')
    await user.click(item.getByRole('button', { name: 'Save' }))

    expect(await screen.findByText('Main passport')).toBeInTheDocument()
    expect(requests.find((r) => r.method === 'PATCH')).toEqual({
      method: 'PATCH',
      url: '/documents/2/',
      body: { name: 'Main passport', expiration_date: '2035-06-01' },
    })
  })

  it('deleting the active version makes the previous one active', async () => {
    const { requests, user } = await openFolder()
    const item = versionItem('Passport 2025')

    await user.click(item.getByRole('button', { name: 'Delete' }))
    expect(
      item.getByText(
        /newest replaced version of this folder will become active/,
      ),
    ).toBeInTheDocument()
    await user.click(item.getByRole('button', { name: 'Yes, delete' }))

    await expect.poll(() => screen.queryByText('Passport 2025')).toBeNull()
    expect(requests).toContainEqual({ method: 'DELETE', url: '/documents/2/' })
    expect(versionItem('Passport 2020').getByText('Active')).toBeInTheDocument()
  })

  it('cancels deletion', async () => {
    const { requests, user } = await openFolder()
    const item = versionItem('Passport 2020')

    await user.click(item.getByRole('button', { name: 'Delete' }))
    await user.click(item.getByRole('button', { name: 'Cancel' }))

    expect(screen.getByText('Passport 2020')).toBeInTheDocument()
    expect(requests.filter((r) => r.method === 'DELETE')).toEqual([])
  })

  it('uploads a new version with the folder type preselected', async () => {
    const { user } = await openFolder()

    await user.click(screen.getByRole('button', { name: 'Upload new version' }))
    const dialog = within(await screen.findByRole('dialog'))

    expect(await dialog.findByLabelText('Document type')).toHaveDisplayValue(
      'Passport',
    )
    await user.upload(
      dialog.getByLabelText('File'),
      new File(['x'], 'passport-2026.pdf', { type: 'application/pdf' }),
    )
    await user.type(dialog.getByLabelText('Expiration date'), '2036-01-01')
    await user.click(dialog.getByRole('button', { name: 'Upload' }))

    expect(await screen.findByText('passport-2026')).toBeInTheDocument()
    expect(versionItem('passport-2026').getByText('Active')).toBeInTheDocument()
    expect(
      versionItem('Passport 2025').getByText('Replaced'),
    ).toBeInTheDocument()
  })

  it('shows not found for an unknown folder', async () => {
    mockDocumentsApi()
    signInAs()
    renderApp('/documents/999')

    expect(await screen.findByRole('alert')).toHaveTextContent('Not found.')
  })
})
