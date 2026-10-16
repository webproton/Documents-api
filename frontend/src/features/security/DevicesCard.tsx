import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { parseApiError } from '@/api/errors'
import { securityApi, type UserDevice } from '@/api/security'
import { Alert } from '@/components/ui/Alert'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { formatDate, formatDateTime } from '@/lib/format'
import { describeUserAgent } from '@/lib/userAgent'

const devicesQueryKey = ['devices'] as const

function Badge({
  tone,
  children,
}: {
  tone: 'blue' | 'green' | 'slate'
  children: string
}) {
  const tones = {
    blue: 'bg-blue-100 text-blue-700',
    green: 'bg-green-100 text-green-700',
    slate: 'bg-slate-100 text-slate-600',
  }
  return (
    <span className={`rounded-full px-2 py-0.5 text-xs ${tones[tone]}`}>
      {children}
    </span>
  )
}

function DeviceRow({
  device,
  onEnd,
  ending,
}: {
  device: UserDevice
  onEnd: () => void
  ending: boolean
}) {
  return (
    <li className="flex flex-wrap items-start justify-between gap-3 py-4">
      <div className="flex flex-col gap-1">
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-medium">
            {describeUserAgent(device.user_agent)}
          </span>
          {device.is_current && <Badge tone="blue">This device</Badge>}
          {device.is_active_session ? (
            <Badge tone="green">Signed in</Badge>
          ) : (
            <Badge tone="slate">Signed out</Badge>
          )}
          {device.is_trusted && device.trusted_until && (
            <Badge tone="slate">
              {`Trusted until ${formatDate(device.trusted_until)}`}
            </Badge>
          )}
        </div>
        <p className="text-sm text-slate-500">
          {device.location || 'Unknown location'} ·{' '}
          {device.ip_address ?? 'Unknown IP'}
          {device.last_login_at &&
            ` · Last login ${formatDateTime(device.last_login_at)}`}
        </p>
      </div>

      {/* The current session ends with "Log out" in the header */}
      {!device.is_current && (
        <Button variant="secondary" loading={ending} onClick={onEnd}>
          End session
        </Button>
      )}
    </li>
  )
}

/** Devices/sessions of the account; ending one revokes its tokens and trust. */
export function DevicesCard() {
  const queryClient = useQueryClient()
  const devices = useQuery({
    queryKey: devicesQueryKey,
    queryFn: securityApi.listDevices,
  })
  const refreshDevices = () =>
    queryClient.invalidateQueries({ queryKey: devicesQueryKey })

  const revoke = useMutation({
    mutationFn: securityApi.revokeDevice,
    onSuccess: refreshDevices,
  })
  const revokeOthers = useMutation({
    mutationFn: securityApi.revokeOtherDevices,
    onSuccess: refreshDevices,
  })

  const actionError = revoke.error ?? revokeOthers.error
  const hasOthers = devices.data?.some((device) => !device.is_current)

  return (
    <Card
      title="Devices and sessions"
      description="Ending a session signs that device out and removes its trusted status, so it will need your password and 2FA again."
    >
      {devices.isPending && <p className="text-sm text-slate-500">Loading…</p>}
      {devices.isError && (
        <Alert variant="error">{parseApiError(devices.error).message}</Alert>
      )}
      {actionError && (
        <Alert variant="error">{parseApiError(actionError).message}</Alert>
      )}
      {revokeOthers.isSuccess && (
        <Alert variant="success">{revokeOthers.data.message}</Alert>
      )}

      {devices.data && (
        <>
          <ul className="divide-y divide-slate-200">
            {devices.data.map((device) => (
              <DeviceRow
                key={device.id}
                device={device}
                ending={revoke.isPending && revoke.variables === device.id}
                onEnd={() => revoke.mutate(device.id)}
              />
            ))}
          </ul>
          {hasOthers && (
            <Button
              variant="secondary"
              className="mt-2"
              loading={revokeOthers.isPending}
              onClick={() => revokeOthers.mutate()}
            >
              End all other sessions
            </Button>
          )}
        </>
      )}
    </Card>
  )
}
