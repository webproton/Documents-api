import { isAxiosError } from 'axios'

/** Normalized error used by forms and toasts. */
export interface ApiError {
  /** HTTP status, null when the server was not reached. */
  status: number | null
  /** One human-readable message for the whole error. */
  message: string
  /** First message per field, e.g. { email: 'Email already exists' }. */
  fieldErrors: Record<string, string>
}

const NETWORK_MESSAGE = 'Server is unavailable. Check your connection.'
const FALLBACK_MESSAGE = 'Something went wrong. Please try again.'

// Keys that describe the whole request rather than a form field
const GENERAL_KEYS = ['detail', 'error', 'non_field_errors']

/** Pick the first string from a DRF error value: "msg" | ["msg"] | {nested}. */
function firstMessage(value: unknown): string | null {
  if (typeof value === 'string') return value
  if (Array.isArray(value)) {
    for (const item of value) {
      const msg = firstMessage(item)
      if (msg) return msg
    }
    return null
  }
  if (value && typeof value === 'object') {
    return firstMessage(Object.values(value))
  }
  return null
}

/**
 * Convert any API failure into ApiError.
 *
 * Handles the shapes the backend produces:
 * - custom exception handler: {"status": "error", "errors": <DRF data>}
 * - views returning errors directly: {"error": "..."} or {"detail": "..."}
 * - DRF data itself: {"field": ["msg"]}, {"non_field_errors": [...]}, ["msg"]
 */
export function parseApiError(error: unknown): ApiError {
  if (!isAxiosError(error)) {
    return { status: null, message: FALLBACK_MESSAGE, fieldErrors: {} }
  }
  if (!error.response) {
    return { status: null, message: NETWORK_MESSAGE, fieldErrors: {} }
  }

  const { status, data } = error.response
  const body: unknown =
    data && typeof data === 'object' && 'errors' in data ? data.errors : data

  const fieldErrors: Record<string, string> = {}
  let general: string | null = null

  if (body && typeof body === 'object' && !Array.isArray(body)) {
    for (const [key, value] of Object.entries(body)) {
      const msg = firstMessage(value)
      if (!msg) continue
      if (GENERAL_KEYS.includes(key)) general ??= msg
      else fieldErrors[key] = msg
    }
  } else {
    general = firstMessage(body)
  }

  const message = general ?? Object.values(fieldErrors)[0] ?? FALLBACK_MESSAGE
  return { status, message, fieldErrors }
}
