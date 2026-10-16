import { useQuery } from '@tanstack/react-query'
import { Link, useParams } from 'react-router'

import { parseApiError } from '@/api/errors'
import { notificationsApi } from '@/api/notifications'
import { Alert } from '@/components/ui/Alert'
import { formatDateTime } from '@/lib/format'
import { paths } from '@/routes/paths'

import { statusTones } from './notificationLabels'

/** One notification with the email as it was sent. */
export function NotificationPage() {
  const notificationId = Number(useParams().notificationId)
  const notification = useQuery({
    queryKey: ['notification', notificationId],
    queryFn: () => notificationsApi.get(notificationId),
    enabled: Number.isInteger(notificationId),
  })
  const data = notification.data

  return (
    <div className="flex max-w-4xl flex-col gap-6">
      <Link
        to={paths.notifications}
        className="text-sm text-blue-600 hover:underline"
      >
        ← All notifications
      </Link>

      {notification.isPending && <p className="text-slate-500">Loading…</p>}
      {notification.isError && (
        <Alert variant="error">
          {parseApiError(notification.error).message}
        </Alert>
      )}

      {data && (
        <>
          <div className="flex flex-col gap-2">
            <h1 className="text-2xl font-semibold">{data.title}</h1>
            <div className="flex flex-wrap items-center gap-2 text-sm text-slate-500">
              <span>{data.type_display}</span>
              <span
                className={`rounded-full px-2 py-0.5 text-xs ${statusTones[data.status]}`}
              >
                {data.status_display}
              </span>
              <span>To {data.recipient_email}</span>
              <span>
                ·{' '}
                {data.sent_at
                  ? `Sent ${formatDateTime(data.sent_at)}`
                  : `Created ${formatDateTime(data.created)}`}
              </span>
            </div>
          </div>

          {/*
            The email body is HTML from the backend templates. An empty
            sandbox runs no scripts, cannot touch this page and keeps the
            email's styles away from the app.
          */}
          <iframe
            title="Email content"
            sandbox=""
            srcDoc={data.message}
            className="h-[60vh] w-full rounded-xl border border-slate-200 bg-white"
          />
        </>
      )}
    </div>
  )
}
