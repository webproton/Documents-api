// Mirrors settings.ALLOWED_DOCUMENT_EXTENSIONS and DOCUMENT_MAX_SIZE
export const DOCUMENT_EXTENSIONS = ['.pdf', '.xls', '.xlsx', '.csv']
export const DOCUMENT_MAX_BYTES = 10 * 1024 * 1024

/** Client-side file check; returns an error message or null. */
export function validateDocumentFile(file: File): string | null {
  const dot = file.name.lastIndexOf('.')
  const extension = dot >= 0 ? file.name.slice(dot).toLowerCase() : ''
  if (!DOCUMENT_EXTENSIONS.includes(extension)) {
    return `Unsupported file format. Allowed: ${DOCUMENT_EXTENSIONS.join(', ')}`
  }
  if (file.size > DOCUMENT_MAX_BYTES) return 'File must be at most 10MB'
  return null
}

/** Backend message when the plan's upload limit is reached (field document_type). */
export function isDocumentLimitError(message: string): boolean {
  return message.startsWith('Document limit reached')
}

/** A document is "expiring" 30 days before its date (same rule as reminders). */
export const EXPIRING_SOON_DAYS = 30

export type ExpiryState = 'expired' | 'expiring' | 'valid'

/** Whole days from today to a "YYYY-MM-DD" date in the user's time zone. */
export function daysUntil(isoDate: string, today = new Date()): number {
  const [year, month, day] = isoDate.split('-').map(Number)
  const target = Date.UTC(year, month - 1, day)
  const now = Date.UTC(today.getFullYear(), today.getMonth(), today.getDate())
  return Math.round((target - now) / 86_400_000)
}

export function expiryState(isoDate: string, today = new Date()): ExpiryState {
  const days = daysUntil(isoDate, today)
  if (days < 0) return 'expired'
  if (days <= EXPIRING_SOON_DAYS) return 'expiring'
  return 'valid'
}
