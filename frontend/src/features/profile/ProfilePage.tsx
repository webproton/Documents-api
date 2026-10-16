import { parseApiError } from '@/api/errors'
import { Alert } from '@/components/ui/Alert'

import { AvatarCard } from './AvatarCard'
import { NameForm } from './NameForm'
import { PasswordForm } from './PasswordForm'
import { useProfile } from './useProfile'

export function ProfilePage() {
  const profile = useProfile()

  return (
    <div className="flex max-w-2xl flex-col gap-6">
      <h1 className="text-2xl font-semibold">Profile</h1>

      {profile.isPending && <p className="text-slate-500">Loading profile…</p>}
      {profile.isError && (
        <Alert variant="error">{parseApiError(profile.error).message}</Alert>
      )}
      {profile.data && (
        <>
          <AvatarCard profile={profile.data} />
          <NameForm profile={profile.data} />
          <PasswordForm />
        </>
      )}
    </div>
  )
}
