import type { DocumentRequest, RequestStatus } from '@/api/requests'

/** Mirrors DocumentRequest.resend_notification: once per hour. */
export const RESEND_INTERVAL_MS = 60 * 60 * 1000

/** PENDING past its deadline is already unusable (the backend task may lag). */
export function effectiveStatus(
  request: Pick<DocumentRequest, 'status' | 'expires_at'>,
  now = new Date(),
): RequestStatus {
  if (request.status === 'PENDING' && new Date(request.expires_at) < now) {
    return 'EXPIRED'
  }
  return request.status
}

/** When the email can be sent again, or null if it can be sent now. */
export function nextResendAt(
  request: Pick<DocumentRequest, 'last_sent_at'>,
  now = new Date(),
): Date | null {
  if (!request.last_sent_at) return null
  const next = new Date(
    new Date(request.last_sent_at).getTime() + RESEND_INTERVAL_MS,
  )
  return next > now ? next : null
}

export const statusLabels: Record<RequestStatus, string> = {
  PENDING: 'Pending',
  COMPLETED: 'Completed',
  CANCELED: 'Canceled',
  EXPIRED: 'Expired',
}

export const statusTones: Record<RequestStatus, string> = {
  PENDING: 'bg-amber-100 text-amber-800',
  COMPLETED: 'bg-green-100 text-green-700',
  CANCELED: 'bg-slate-100 text-slate-600',
  EXPIRED: 'bg-red-100 text-red-700',
}
