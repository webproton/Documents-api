import { formatDay } from '@/lib/format'

import { daysUntil, expiryState } from './documentRules'

/** Expiration date with a warning when expired or expiring within 30 days. */
export function ExpiryBadge({ date }: { date: string | null }) {
  if (!date) return <span className="text-slate-400">No expiration date</span>

  const state = expiryState(date)
  const days = daysUntil(date)

  return (
    <span className="inline-flex flex-wrap items-center gap-2">
      <span>Expires {formatDay(date)}</span>
      {state === 'expired' && (
        <span className="rounded-full bg-red-100 px-2 py-0.5 text-xs text-red-700">
          Expired
        </span>
      )}
      {state === 'expiring' && (
        <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs text-amber-800">
          {days === 0
            ? 'Expires today'
            : `In ${days} day${days === 1 ? '' : 's'}`}
        </span>
      )}
    </span>
  )
}
