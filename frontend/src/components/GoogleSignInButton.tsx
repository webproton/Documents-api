import { useEffect, useRef, useState } from 'react'

import { getGoogleClientId, loadGoogleIdentity } from '@/lib/google'

interface GoogleSignInButtonProps {
  /** Receives the Google ID token after the user picks an account. */
  onCredential: (idToken: string) => void
  text?: 'signin_with' | 'signup_with'
}

/**
 * Google-rendered "Sign in with Google" button.
 * Renders nothing when VITE_GOOGLE_CLIENT_ID is not configured.
 */
export function GoogleSignInButton({
  onCredential,
  text = 'signin_with',
}: GoogleSignInButtonProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  // Latest callback without re-initializing Google on every render
  const onCredentialRef = useRef(onCredential)
  const [loadError, setLoadError] = useState(false)
  const clientId = getGoogleClientId()

  useEffect(() => {
    onCredentialRef.current = onCredential
  }, [onCredential])

  useEffect(() => {
    if (!clientId) return
    let cancelled = false

    loadGoogleIdentity()
      .then((googleId) => {
        if (cancelled || !containerRef.current) return
        googleId.initialize({
          client_id: clientId,
          callback: ({ credential }) => onCredentialRef.current(credential),
        })
        googleId.renderButton(containerRef.current, {
          theme: 'outline',
          size: 'large',
          text,
          width: 320,
        })
      })
      .catch(() => !cancelled && setLoadError(true))

    return () => {
      cancelled = true
    }
  }, [clientId, text])

  if (!clientId) return null
  if (loadError) {
    return (
      <p className="text-center text-sm text-slate-500">
        Google sign-in is unavailable right now.
      </p>
    )
  }
  return <div ref={containerRef} className="flex justify-center" />
}
