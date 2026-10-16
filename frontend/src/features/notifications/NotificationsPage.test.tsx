import { screen, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import type { NotificationDetail, NotificationItem } from '@/api/notifications'
import { api, apiError, server } from '@/test/server'
import { renderApp, signInAs } from '@/test/utils'

const item = (overrides: Partial<NotificationItem>): NotificationItem => ({
  id: 1,
  title: 'Document Request: Passport',
  type: 'DOCUMENT_REQUEST',
  status: 'SENT',
  recipient_email: 'anna@example.com',
  created: '2026-10-10T09:00:00Z',
  sent_at: '2026-10-10T09:00:05Z',
  ...overrides,
})

function mockNotificationsApi(items: NotificationItem[]) {
  const queries: string[] = []
  server.use(
    http.get(api('/notifications/'), ({ request }) => {
      queries.push(new URL(request.url).search)
      return HttpResponse.json(items)
    }),
  )
  return { queries }
}

describe('NotificationsPage', () => {
  it('lists notifications with type, recipient, status and date', async () => {
    mockNotificationsApi([
      item({ id: 1 }),
      item({
        id: 2,
        title: 'Your document expires soon',
        type: 'REMINDER',
        status: 'FAILED',
        recipient_email: 'user@example.com',
      }),
    ])
    signInAs()
    renderApp('/notifications')

    const rows = await screen.findAllByRole('listitem')
    expect(rows).toHaveLength(2)
    expect(
      within(rows[0]).getByText('Document Request: Passport'),
    ).toBeInTheDocument()
    expect(
      within(rows[0]).getByText(/Document request · To anna@example.com/),
    ).toBeInTheDocument()
    expect(within(rows[0]).getByText('Sent')).toBeInTheDocument()
    expect(within(rows[1]).getByText(/Expiration reminder/)).toBeInTheDocument()
    expect(within(rows[1]).getByText('Failed')).toBeInTheDocument()
    expect(within(rows[0]).getByRole('link')).toHaveAttribute(
      'href',
      '/notifications/1',
    )
  })

  it('sends type, status, date range and ordering filters', async () => {
    const { queries } = mockNotificationsApi([item({})])
    signInAs()
    const { user, router } = renderApp('/notifications')
    await screen.findAllByRole('listitem')

    await user.selectOptions(screen.getByLabelText('Type'), 'REMINDER')
    await user.selectOptions(screen.getByLabelText('Status'), 'SENT')
    await user.type(screen.getByLabelText('From'), '2026-10-01')
    await user.type(screen.getByLabelText('To'), '2026-10-16')
    await user.selectOptions(screen.getByLabelText('Sort'), 'created')

    const last = new URLSearchParams(queries.at(-1))
    expect(Object.fromEntries(last)).toEqual({
      type: 'REMINDER',
      status: 'SENT',
      created_after: '2026-10-01',
      // "To" includes the whole selected day
      created_before: '2026-10-16T23:59:59',
      ordering: 'created',
    })
    expect(router.state.location.search).toContain('type=REMINDER')
  })

  it('restores filters from the URL', async () => {
    const { queries } = mockNotificationsApi([])
    signInAs()
    renderApp('/notifications?status=FAILED')

    expect(
      await screen.findByText('No notifications match these filters.'),
    ).toBeInTheDocument()
    expect(screen.getByLabelText('Status')).toHaveValue('FAILED')
    expect(queries[0]).toContain('status=FAILED')
  })

  it('explains an empty inbox', async () => {
    mockNotificationsApi([])
    signInAs()
    renderApp('/notifications')

    expect(await screen.findByText('No notifications yet.')).toBeInTheDocument()
  })
})

describe('NotificationPage', () => {
  const detail: NotificationDetail = {
    ...item({ id: 5 }),
    message:
      '<p>Please upload your <b>Passport</b>.</p><script>alert(1)</script>',
    type_display: 'Document Request',
    status_display: 'Sent',
    document: 12,
  }

  it('shows the email in a sandboxed frame', async () => {
    server.use(
      http.get(api('/notifications/5/'), () => HttpResponse.json(detail)),
    )
    signInAs()
    renderApp('/notifications/5')

    expect(
      await screen.findByRole('heading', {
        name: 'Document Request: Passport',
      }),
    ).toBeInTheDocument()
    expect(screen.getByText('To anna@example.com')).toBeInTheDocument()
    const frame = screen.getByTitle('Email content')
    // Empty sandbox: no scripts, no access to the app
    expect(frame).toHaveAttribute('sandbox', '')
    expect(frame).toHaveAttribute('srcdoc', detail.message)
  })

  it('shows not found for someone else’s or unknown notification', async () => {
    server.use(
      http.get(api('/notifications/99/'), () =>
        apiError(404, { detail: 'No Notification matches the given query.' }),
      ),
    )
    signInAs()
    renderApp('/notifications/99')

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'No Notification matches the given query.',
    )
  })
})
