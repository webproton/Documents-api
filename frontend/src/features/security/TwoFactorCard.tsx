import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'
import { Link } from 'react-router'

import type { Profile } from '@/api/profile'
import { securityApi } from '@/api/security'
import { Alert } from '@/components/ui/Alert'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { TextField } from '@/components/ui/TextField'
import { useRefreshProfile } from '@/features/profile/useProfile'
import { applyApiError } from '@/lib/forms'
import { paths } from '@/routes/paths'

import {
  twoFactorSettingsSchema,
  type TwoFactorSettingsValues,
} from './schemas'

const methodLabels = { EMAIL: 'Email', SMS: 'SMS' } as const

/** Turn 2FA on/off and choose how codes are delivered (password required). */
export function TwoFactorCard({ profile }: { profile: Profile }) {
  const refreshProfile = useRefreshProfile()
  const enabled = profile.is_2fa_enabled

  const {
    register,
    handleSubmit,
    setError,
    resetField,
    formState: { errors },
  } = useForm<TwoFactorSettingsValues>({
    resolver: zodResolver(twoFactorSettingsSchema),
    defaultValues: { method: profile.two_factor_method, password: '' },
  })

  const toggle = useMutation({
    mutationFn: securityApi.toggleTwoFactor,
    onSuccess: () => {
      resetField('password')
      return refreshProfile()
    },
    onError: (error) => applyApiError(error, setError, ['method', 'password']),
  })

  const submit = (enable: boolean) =>
    handleSubmit(({ method, password }) =>
      toggle.mutate({ enable, password, method }),
    )

  const status = enabled
    ? `On · codes are sent by ${methodLabels[profile.two_factor_method]}`
    : 'Off'

  return (
    <Card
      title="Two-factor authentication"
      description="On a new device you will enter a one-time code after your password."
    >
      <p className="mb-4 text-sm">
        Status: <span className="font-medium">{status}</span>
      </p>

      {!profile.has_password ? (
        <Alert>
          2FA settings are confirmed with your password.{' '}
          <Link to={paths.profile} className="font-medium underline">
            Set a password
          </Link>{' '}
          first.
        </Alert>
      ) : (
        <form noValidate className="flex flex-col gap-4">
          {errors.root && <Alert variant="error">{errors.root.message}</Alert>}
          {toggle.isSuccess && (
            <Alert variant="success">{toggle.data.message}</Alert>
          )}

          <fieldset className="flex flex-col gap-2">
            <legend className="mb-1 text-sm font-medium text-slate-700">
              Send codes by
            </legend>
            <label className="flex items-center gap-2 text-sm">
              <input type="radio" value="EMAIL" {...register('method')} />
              Email ({profile.email})
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="radio"
                value="SMS"
                disabled={!profile.phone_confirmed}
                {...register('method')}
              />
              SMS
              {profile.phone_confirmed
                ? ` (${profile.phone_number})`
                : ' — confirm a phone number below first'}
            </label>
            {errors.method && (
              <p className="text-sm text-red-600">{errors.method.message}</p>
            )}
          </fieldset>

          <TextField
            label="Password"
            type="password"
            autoComplete="current-password"
            error={errors.password?.message}
            {...register('password')}
          />

          <div className="flex flex-wrap gap-2">
            <Button
              type="submit"
              loading={toggle.isPending && toggle.variables?.enable}
              onClick={submit(true)}
            >
              {enabled ? 'Save method' : 'Turn on 2FA'}
            </Button>
            {enabled && (
              <Button
                type="button"
                variant="secondary"
                loading={toggle.isPending && !toggle.variables?.enable}
                onClick={submit(false)}
              >
                Turn off 2FA
              </Button>
            )}
          </div>
        </form>
      )}
    </Card>
  )
}
