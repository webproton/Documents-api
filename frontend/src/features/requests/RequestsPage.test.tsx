import { screen, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import type { DocumentRequest } from '@/api/requests'
import { PASSPORT, VISA } from '@/features/documents/documentsMock'
import { api, apiError, server } from '@/test/server'
import { renderApp, signInAs } from '@/test/utils'

const hoursAgo = (hours: number) =>
  new Date(Date.now() - hours * 3_600_000).toISOString()
const daysFromNow = (days: number) =>
  new Date(Date.now() + days * 86_400_000).toISOString()

const docRequest = (overrides: Partial<DocumentRequest>): DocumentRequest => ({
  id: 1,
  recipient_email: 'anna@example.com',
  document_type: PASSPORT.id,
  document_type_name: PASSPORT.name,
  token: '9b2c5c3e-0000-4000-8000-000000000001',
  status: 'PENDING',
  created: hoursAgo(5),
  expires_at: daysFromNow(25),
  last_sent_at: hoursAgo(5),
  ...overrides,
})

/** In-memory requests backend with the resend (1 h) and cancel rules. */
function mockRequestsApi(initial: DocumentRequest[] = []) {
  let requests = [...initial]
  const calls: { url: string; body?: unknown }[] = []
  server.use(
    http.get(api('/documents/types/'), () =>
      HttpResponse.json([PASSPORT, VISA]),
    ),
    http.get(api('/documents/requests/'), () => HttpResponse.json(requests)),
    http.post(api('/documents/requests/'), async ({ request }) => {
      const body = (await request.json()) as {
        recipient_email: string
        document_type: number
      }
      calls.push({ url: '/requests/', body })
      const created = docRequest({
        id: requests.length + 10,
        ...body,
        document_type_name:
          body.document_type === VISA.id ? 'Visa' : 'Passport',
        created: new Date().toISOString(),
        last_sent_at: new Date().toISOString(),
      })
      requests = [created, ...requests]
      return HttpResponse.json(created, { status: 201 })
    }),
    http.post(api('/documents/requests/:id/resend/'), ({ params }) => {
      calls.push({ url: `/requests/${params.id}/resend/` })
      requests = requests.map((r) =>
        r.id === Number(params.id)
          ? { ...r, last_sent_at: new Date().toISOString() }
          : r,
      )
      return HttpResponse.json({ detail: 'Notification resent successfully.' })
    }),
    http.post(api('/documents/requests/:id/cancel/'), ({ params }) => {
      calls.push({ url: `/requests/${params.id}/cancel/` })
      requests = requests.map((r) =>
        r.id === Number(params.id) ? { ...r, status: 'CANCELED' } : r,
      )
      return HttpResponse.json({
        detail: 'Document request has been canceled.',
      })
    }),
  )
  return { calls }
}

async function openRequests(initial?: DocumentRequest[]) {
  const mock = mockRequestsApi(initial)
  signInAs()
  const app = renderApp('/requests')
  // Wait for the list itself, not just the page heading
  if (initial?.length) await screen.findAllByText(/^To /)
  else await screen.findByText('No requests sent yet.')
  return { ...mock, ...app }
}

/** The list row of the request sent to this email. */
const rowOf = (recipientLine: string) =>
  within(
    screen
      .getByText(new RegExp(`^${recipientLine.replace(/[.+]/g, '\\$&')}\\b`))
      .closest('li') as HTMLElement,
  )

describe('RequestsPage', () => {
  it('sends a new request and lists it', async () => {
    const { calls, user } = await openRequests()

    await user.type(screen.getByLabelText('Recipient email'), 'bob@example.com')
    await user.selectOptions(
      await screen.findByLabelText('Document type'),
      'Visa',
    )
    await user.click(screen.getByRole('button', { name: 'Send request' }))

    expect(
      await screen.findByText('Request sent to bob@example.com.'),
    ).toBeInTheDocument()
    expect(calls).toEqual([
      {
        url: '/requests/',
        body: { recipient_email: 'bob@example.com', document_type: VISA.id },
      },
    ])
    expect(await screen.findByText(/To bob@example.com/)).toBeInTheDocument()
    // The form is ready for the next request
    expect(screen.getByLabelText('Recipient email')).toHaveValue('')
  })

  it('validates the form', async () => {
    const { calls, user } = await openRequests()

    await user.click(screen.getByRole('button', { name: 'Send request' }))

    expect(
      await screen.findByText('Enter a valid email address'),
    ).toBeInTheDocument()
    expect(screen.getByText('Choose a document type')).toBeInTheDocument()
    expect(calls).toEqual([])
  })

  it('shows type, recipient, date and status of each request', async () => {
    await openRequests([
      docRequest({ id: 1 }),
      docRequest({ id: 2, recipient_email: 'c@x.com', status: 'COMPLETED' }),
      docRequest({ id: 3, recipient_email: 'd@x.com', status: 'CANCELED' }),
      // Still PENDING in the DB, but the deadline has passed
      docRequest({
        id: 4,
        recipient_email: 'e@x.com',
        expires_at: hoursAgo(1),
      }),
    ])

    expect(
      rowOf('To anna@example.com').getByText('Pending'),
    ).toBeInTheDocument()
    expect(rowOf('To c@x.com').getByText('Completed')).toBeInTheDocument()
    expect(rowOf('To d@x.com').getByText('Canceled')).toBeInTheDocument()
    expect(rowOf('To e@x.com').getByText('Expired')).toBeInTheDocument()
    // Actions only for usable (pending) requests
    expect(
      rowOf('To e@x.com').queryByRole('button', { name: 'Resend email' }),
    ).not.toBeInTheDocument()
  })

  it('resends the email at most once per hour', async () => {
    const { calls, user } = await openRequests([
      docRequest({ id: 1, last_sent_at: hoursAgo(2) }),
      docRequest({
        id: 2,
        recipient_email: 'recent@x.com',
        last_sent_at: hoursAgo(0.5),
      }),
    ])

    expect(
      rowOf('To recent@x.com').getByRole('button', { name: 'Resend email' }),
    ).toBeDisabled()
    expect(
      rowOf('To recent@x.com').getByText(/Email can be resent after/),
    ).toBeInTheDocument()

    await user.click(
      rowOf('To anna@example.com').getByRole('button', {
        name: 'Resend email',
      }),
    )

    expect(
      await screen.findByText('Notification resent successfully.'),
    ).toBeInTheDocument()
    expect(calls).toEqual([{ url: '/requests/1/resend/' }])
    // Just sent → disabled for the next hour
    await expect
      .poll(() =>
        rowOf('To anna@example.com')
          .getByRole('button', { name: 'Resend email' })
          .hasAttribute('disabled'),
      )
      .toBe(true)
  })

  it('shows the backend resend limit error', async () => {
    mockRequestsApi([docRequest({ id: 1, last_sent_at: hoursAgo(2) })])
    server.use(
      http.post(api('/documents/requests/:id/resend/'), () =>
        apiError(400, { detail: 'You can resend notification once per hour.' }),
      ),
    )
    signInAs()
    const { user } = renderApp('/requests')

    await user.click(
      await screen.findByRole('button', { name: 'Resend email' }),
    )

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'You can resend notification once per hour.',
    )
  })

  it('cancels a request after confirmation', async () => {
    const { calls, user } = await openRequests([docRequest({ id: 7 })])

    await user.click(screen.getByRole('button', { name: 'Cancel request' }))
    await user.click(screen.getByRole('button', { name: 'Yes, cancel it' }))

    expect(await screen.findByText('Canceled')).toBeInTheDocument()
    expect(calls).toEqual([{ url: '/requests/7/cancel/' }])
    expect(
      screen.queryByRole('button', { name: 'Cancel request' }),
    ).not.toBeInTheDocument()
  })

  it('copies the upload link', async () => {
    const { user } = await openRequests([docRequest({ id: 1 })])

    await user.click(screen.getByRole('button', { name: 'Copy link' }))

    expect(await navigator.clipboard.readText()).toBe(
      `${window.location.origin}/upload/9b2c5c3e-0000-4000-8000-000000000001`,
    )
    expect(screen.getByRole('button', { name: 'Copied' })).toBeInTheDocument()
  })
})
