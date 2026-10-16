import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation } from '@tanstack/react-query'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Link, Navigate, useLocation } from 'react-router'

import { authApi } from '@/api/auth'
import { parseApiError } from '@/api/errors'
import { Alert } from '@/components/ui/Alert'
import { Button } from '@/components/ui/Button'
import { TextField } from '@/components/ui/TextField'
import { useCountdown } from '@/hooks/useCountdown'
import { paths } from '@/routes/paths'

import { useAuth } from './auth-context'
import { twoFactorSchema, type TwoFactorValues } from './schemas'
import {
  isTwoFactorSessionEnded,
  RESEND_COOLDOWN_SECONDS,
  type TwoFactorState,
} from './two-factor'

/**
 * Second login step: enter the one-time code sent by email or SMS.
 * Reached only from LoginPage, which passes pre_auth_token in router state.
 */
export function TwoFactorPage() {
  const state = useLocation().state as TwoFactorState | null

  // Opened directly (no pre_auth_token): start from the first step
  if (!state?.preAuthToken) return <Navigate to={paths.login} replace />

  return <TwoFactorForm {...state} />
}

function TwoFactorForm({ preAuthToken, message }: TwoFactorState) {
  const { signIn } = useAuth()
  const [sessionEnded, setSessionEnded] = useState<string | null>(null)
  const [notice, setNotice] = useState(message)
  const cooldown = useCountdown(RESEND_COOLDOWN_SECONDS)

  const {
    register,
    handleSubmit,
    setError,
    resetField,
    formState: { errors },
  } = useForm<TwoFactorValues>({
    resolver: zodResolver(twoFactorSchema),
    defaultValues: { code: '', rememberDevice: true },
  })

  /** Session-ending errors replace the form; others stay on it. */
  const handleError = (error: unknown) => {
    const { message: errorMessage } = parseApiError(error)
    if (isTwoFactorSessionEnded(errorMessage)) setSessionEnded(errorMessage)
    else setError('root', { type: 'server', message: errorMessage })
  }

  const verify = useMutation({
    mutationFn: authApi.verifyTwoFactor,
    onSuccess: signIn,
    onError: (error) => {
      resetField('code')
      handleError(error)
    },
  })

  const resend = useMutation({
    mutationFn: () => authApi.resendTwoFactor(preAuthToken),
    onSuccess: (data) => {
      setNotice(data.message)
      cooldown.restart()
    },
    onError: handleError,
  })

  if (sessionEnded) {
    return (
      <div className="flex flex-col gap-4 text-center">
        <h1 className="text-2xl font-semibold">Two-factor authentication</h1>
        <Alert variant="error">{sessionEnded}</Alert>
        <Link
          to={paths.login}
          className="text-sm text-blue-600 hover:underline"
        >
          Back to log in
        </Link>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-2">
        <h1 className="text-2xl font-semibold">Two-factor authentication</h1>
        <Alert>{notice}</Alert>
      </div>

      <form
        noValidate
        className="flex flex-col gap-4"
        onSubmit={handleSubmit(({ code, rememberDevice }) =>
          verify.mutate({
            pre_auth_token: preAuthToken,
            code,
            remember_device: rememberDevice,
          }),
        )}
      >
        {errors.root && <Alert variant="error">{errors.root.message}</Alert>}

        <TextField
          label="Verification code"
          inputMode="numeric"
          autoComplete="one-time-code"
          maxLength={6}
          autoFocus
          error={errors.code?.message}
          {...register('code')}
        />

        <label className="flex items-center gap-2 text-sm text-slate-700">
          <input type="checkbox" {...register('rememberDevice')} />
          Trust this device for 90 days
        </label>

        <Button type="submit" loading={verify.isPending}>
          Verify
        </Button>
      </form>

      <div className="flex flex-col items-center gap-2 text-sm">
        <Button
          variant="secondary"
          disabled={cooldown.remaining > 0}
          loading={resend.isPending}
          onClick={() => resend.mutate()}
        >
          {cooldown.remaining > 0
            ? `Resend code in ${cooldown.remaining}s`
            : 'Resend code'}
        </Button>
        <Link to={paths.login} className="text-slate-500 hover:underline">
          Use a different account
        </Link>
      </div>
    </div>
  )
}
