import type { NotificationStatus, NotificationType } from '@/api/notifications'

export const typeLabels: Record<NotificationType, string> = {
  EMAIL_CONFIRMATION: 'Email confirmation',
  DOCUMENT_REQUEST: 'Document request',
  REMINDER: 'Expiration reminder',
}

export const statusLabels: Record<NotificationStatus, string> = {
  PENDING: 'Pending',
  SENT: 'Sent',
  FAILED: 'Failed',
}

export const statusTones: Record<NotificationStatus, string> = {
  PENDING: 'bg-amber-100 text-amber-800',
  SENT: 'bg-green-100 text-green-700',
  FAILED: 'bg-red-100 text-red-700',
}

/**
 * The API filters by datetime. A "to" date from a date input means
 * "up to the end of that day", not its midnight.
 */
export function endOfDay(isoDate: string): string {
  return `${isoDate}T23:59:59`
}
