import { apiClient } from './client'

export type NotificationType =
  'EMAIL_CONFIRMATION' | 'DOCUMENT_REQUEST' | 'REMINDER'

export type NotificationStatus = 'PENDING' | 'SENT' | 'FAILED'

/** An email the system sent (or tried to send) for the user. */
export interface NotificationItem {
  id: number
  title: string
  type: NotificationType
  status: NotificationStatus
  recipient_email: string
  created: string
  sent_at: string | null
}

export interface NotificationDetail extends NotificationItem {
  /** Rendered HTML body of the email */
  message: string
  type_display: string
  status_display: string
  document: number | null
}

export interface NotificationFilters {
  type?: NotificationType | ''
  status?: NotificationStatus | ''
  /** ISO datetime (DateTimeFilter) */
  created_after?: string
  created_before?: string
  ordering?: 'created' | '-created' | 'sent_at' | '-sent_at'
}

const compact = (params: object) =>
  Object.fromEntries(Object.entries(params).filter(([, value]) => value))

export const notificationsApi = {
  list: (filters: NotificationFilters = {}) =>
    apiClient
      .get<NotificationItem[]>('/notifications/', { params: compact(filters) })
      .then((res) => res.data),

  get: (id: number) =>
    apiClient
      .get<NotificationDetail>(`/notifications/${id}/`)
      .then((res) => res.data),
}
