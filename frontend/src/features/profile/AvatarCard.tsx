import { useMutation } from '@tanstack/react-query'
import { useState, type ChangeEvent } from 'react'

import { parseApiError } from '@/api/errors'
import { profileApi, type Profile } from '@/api/profile'
import { Alert } from '@/components/ui/Alert'
import { Card } from '@/components/ui/Card'

import { AVATAR_TYPES, validateAvatar } from './schemas'
import { useRefreshProfile } from './useProfile'

function initials({ first_name, last_name, email }: Profile) {
  const fromName = `${first_name.charAt(0)}${last_name.charAt(0)}`
  return (fromName || email.charAt(0)).toUpperCase()
}

export function AvatarCard({ profile }: { profile: Profile }) {
  const refreshProfile = useRefreshProfile()
  const [clientError, setClientError] = useState<string | null>(null)

  const upload = useMutation({
    mutationFn: profileApi.uploadAvatar,
    onSuccess: refreshProfile,
  })

  const handleFile = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    event.target.value = '' // allow choosing the same file again
    if (!file) return

    const error = validateAvatar(file)
    setClientError(error)
    upload.reset()
    if (!error) upload.mutate(file)
  }

  const error =
    clientError ?? (upload.isError ? parseApiError(upload.error).message : null)

  return (
    <Card title="Photo" description="JPEG or PNG, up to 5 MB.">
      <div className="flex flex-wrap items-center gap-4">
        {profile.avatar ? (
          <img
            src={profile.avatar}
            alt="Your avatar"
            className="size-20 rounded-full object-cover"
          />
        ) : (
          <div
            aria-hidden
            className="flex size-20 items-center justify-center rounded-full bg-slate-200 text-2xl font-semibold text-slate-600"
          >
            {initials(profile)}
          </div>
        )}

        <label className="cursor-pointer rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100">
          {upload.isPending ? 'Uploading…' : 'Change photo'}
          <input
            type="file"
            accept={AVATAR_TYPES.join(',')}
            className="sr-only"
            disabled={upload.isPending}
            onChange={handleFile}
          />
        </label>
      </div>

      <div className="mt-4 empty:hidden">
        {error && <Alert variant="error">{error}</Alert>}
        {upload.isSuccess && <Alert variant="success">Photo updated.</Alert>}
      </div>
    </Card>
  )
}
