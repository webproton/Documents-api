/**
 * Google Identity Services (GIS) — "Sign in with Google" button.
 * https://developers.google.com/identity/gsi/web/reference/js-reference
 *
 * Only the small part of the API we use is typed here.
 */
export interface GoogleCredentialResponse {
  /** Google ID token (JWT) — sent to POST /api/auth/social/google/ */
  credential: string
}

interface GoogleAccountsId {
  initialize(config: {
    client_id: string
    callback: (response: GoogleCredentialResponse) => void
  }): void
  renderButton(
    parent: HTMLElement,
    options: {
      theme?: 'outline' | 'filled_blue'
      size?: 'large' | 'medium'
      text?: 'signin_with' | 'signup_with' | 'continue_with'
      width?: number
    },
  ): void
}

declare global {
  interface Window {
    google?: { accounts: { id: GoogleAccountsId } }
  }
}

const SCRIPT_SRC = 'https://accounts.google.com/gsi/client'

let scriptPromise: Promise<GoogleAccountsId> | null = null

/** Load the GIS script once and resolve with google.accounts.id. */
export function loadGoogleIdentity(): Promise<GoogleAccountsId> {
  if (window.google) return Promise.resolve(window.google.accounts.id)

  scriptPromise ??= new Promise((resolve, reject) => {
    const script = document.createElement('script')
    script.src = SCRIPT_SRC
    script.async = true
    script.onload = () =>
      window.google
        ? resolve(window.google.accounts.id)
        : reject(new Error('Google Identity Services did not initialize'))
    script.onerror = () => {
      scriptPromise = null // allow a retry on the next mount
      reject(new Error('Failed to load Google Identity Services'))
    }
    document.head.append(script)
  })
  return scriptPromise
}

/** OAuth client id shared with the backend (GOOGLE_CLIENT_ID). */
export function getGoogleClientId(): string | undefined {
  return import.meta.env.VITE_GOOGLE_CLIENT_ID || undefined
}
