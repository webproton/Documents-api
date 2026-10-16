import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { generatePath, Link, useSearchParams } from 'react-router'

import { parseApiError } from '@/api/errors'
import {
  notificationsApi,
  type NotificationFilters,
  type NotificationItem,
  type NotificationStatus,
  type NotificationType,
} from '@/api/notifications'
import { Alert } from '@/components/ui/Alert'
import { formatDateTime } from '@/lib/format'
import { paths } from '@/routes/paths'

import {
  endOfDay,
  statusLabels,
  statusTones,
  typeLabels,
} from './notificationLabels'

const inputClass =
  'rounded-md border border-slate-300 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-slate-200'

function NotificationRow({ notification }: { notification: NotificationItem }) {
  return (
    <li>
      <Link
        to={generatePath(paths.notification, {
          notificationId: String(notification.id),
        })}
        className="flex flex-wrap items-start justify-between gap-3 px-6 py-4 hover:bg-slate-50"
      >
        <div className="flex flex-col gap-1">
          <span className="font-medium">{notification.title}</span>
          <span className="text-sm text-slate-500">
            {typeLabels[notification.type] ?? notification.type} · To{' '}
            {notification.recipient_email}
          </span>
        </div>
        <div className="flex flex-col items-end gap-1 text-sm text-slate-500">
          <span
            className={`rounded-full px-2 py-0.5 text-xs ${statusTones[notification.status]}`}
          >
            {statusLabels[notification.status]}
          </span>
          <span>{formatDateTime(notification.created)}</span>
        </div>
      </Link>
    </li>
  )
}

/** Emails sent for the account: confirmations, document requests, reminders. */
export function NotificationsPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const createdFrom = searchParams.get('from') ?? ''
  const createdTo = searchParams.get('to') ?? ''

  // Filters live in the URL: shareable and kept on reload / back
  const filters: NotificationFilters = {
    type: (searchParams.get('type') as NotificationType) ?? '',
    status: (searchParams.get('status') as NotificationStatus) ?? '',
    created_after: createdFrom,
    created_before: createdTo && endOfDay(createdTo),
    ordering:
      searchParams.get('ordering') === 'created' ? 'created' : '-created',
  }

  const setParam = (key: string, value: string) =>
    setSearchParams(
      (params) => {
        if (value) params.set(key, value)
        else params.delete(key)
        return params
      },
      { replace: true },
    )

  const notifications = useQuery({
    queryKey: ['notifications', filters],
    queryFn: () => notificationsApi.list(filters),
    placeholderData: keepPreviousData,
  })

  const hasFilters = Boolean(
    filters.type || filters.status || createdFrom || createdTo,
  )

  return (
    <div className="flex max-w-4xl flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold">Notifications</h1>
        <p className="mt-1 text-sm text-slate-500">
          Emails sent for your account: confirmations, document requests and
          expiration reminders.
        </p>
      </div>

      <div className="flex flex-wrap items-end gap-3">
        <label className="flex flex-col gap-1 text-xs text-slate-500">
          Type
          <select
            value={filters.type}
            onChange={(event) => setParam('type', event.target.value)}
            className={inputClass}
          >
            <option value="">All types</option>
            {Object.entries(typeLabels).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-xs text-slate-500">
          Status
          <select
            value={filters.status}
            onChange={(event) => setParam('status', event.target.value)}
            className={inputClass}
          >
            <option value="">All statuses</option>
            {Object.entries(statusLabels).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-xs text-slate-500">
          From
          <input
            type="date"
            value={createdFrom}
            onChange={(event) => setParam('from', event.target.value)}
            className={inputClass}
          />
        </label>
        <label className="flex flex-col gap-1 text-xs text-slate-500">
          To
          <input
            type="date"
            value={createdTo}
            onChange={(event) => setParam('to', event.target.value)}
            className={inputClass}
          />
        </label>
        <label className="flex flex-col gap-1 text-xs text-slate-500">
          Sort
          <select
            value={filters.ordering}
            onChange={(event) =>
              setParam(
                'ordering',
                event.target.value === 'created' ? 'created' : '',
              )
            }
            className={inputClass}
          >
            <option value="-created">Newest first</option>
            <option value="created">Oldest first</option>
          </select>
        </label>
      </div>

      {notifications.isPending && <p className="text-slate-500">Loading…</p>}
      {notifications.isError && (
        <Alert variant="error">
          {parseApiError(notifications.error).message}
        </Alert>
      )}
      {notifications.data &&
        (notifications.data.length === 0 ? (
          <p className="text-slate-500">
            {hasFilters
              ? 'No notifications match these filters.'
              : 'No notifications yet.'}
          </p>
        ) : (
          <section
            className={`rounded-xl border border-slate-200 bg-white ${
              notifications.isPlaceholderData ? 'opacity-60' : ''
            }`}
          >
            <ul className="divide-y divide-slate-200">
              {notifications.data.map((notification) => (
                <NotificationRow
                  key={notification.id}
                  notification={notification}
                />
              ))}
            </ul>
          </section>
        ))}
    </div>
  )
}
