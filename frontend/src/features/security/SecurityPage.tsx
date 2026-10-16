import { parseApiError } from '@/api/errors'
import { Alert } from '@/components/ui/Alert'
import { useProfile } from '@/features/profile/useProfile'

import { DevicesCard } from './DevicesCard'
import { PhoneCard } from './PhoneCard'
import { TwoFactorCard } from './TwoFactorCard'

export function SecurityPage() {
  const profile = useProfile()

  return (
    <div className="flex max-w-3xl flex-col gap-6">
      <h1 className="text-2xl font-semibold">Security</h1>

      {profile.isPending && <p className="text-slate-500">Loading…</p>}
      {profile.isError && (
        <Alert variant="error">{parseApiError(profile.error).message}</Alert>
      )}
      {profile.data && (
        <>
          <TwoFactorCard profile={profile.data} />
          <PhoneCard profile={profile.data} />
        </>
      )}
      <DevicesCard />
    </div>
  )
}
