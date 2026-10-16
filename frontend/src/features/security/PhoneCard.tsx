import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation } from '@tanstack/react-query'
import { useState } from 'react'
import { useForm } from 'react-hook-form'

import type { Profile } from '@/api/profile'
import { securityApi } from '@/api/security'
import { Alert } from '@/components/ui/Alert'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { TextField } from '@/components/ui/TextField'
import { useRefreshProfile } from '@/features/profile/useProfile'
import { applyApiError } from '@/lib/forms'

import {
  phoneCodeSchema,
  phoneSchema,
  type PhoneCodeValues,
  type PhoneValues,
} from './schemas'

type Step = 'view' | 'enter-phone' | 'enter-code'

/** Phone confirmation by SMS code — required before SMS 2FA. */
export function PhoneCard({ profile }: { profile: Profile }) {
  const refreshProfile = useRefreshProfile()
  const [step, setStep] = useState<Step>(
    profile.phone_confirmed ? 'view' : 'enter-phone',
  )
  const [pendingPhone, setPendingPhone] = useState('')
  const [confirmed, setConfirmed] = useState(false)

  const phoneForm = useForm<PhoneValues>({
    resolver: zodResolver(phoneSchema),
    defaultValues: { phone_number: '' },
  })
  const codeForm = useForm<PhoneCodeValues>({
    resolver: zodResolver(phoneCodeSchema),
    defaultValues: { code: '' },
  })

  const requestCode = useMutation({
    mutationFn: securityApi.requestPhoneConfirmation,
    onSuccess: (_, phone) => {
      setPendingPhone(phone)
      codeForm.reset()
      setStep('enter-code')
    },
    onError: (error) =>
      applyApiError(error, phoneForm.setError, ['phone_number']),
  })

  const confirm = useMutation({
    mutationFn: securityApi.confirmPhone,
    onSuccess: async () => {
      await refreshProfile()
      setConfirmed(true)
      setStep('view')
    },
    onError: (error) => applyApiError(error, codeForm.setError, ['code']),
  })

  return (
    <Card
      title="Phone number"
      description="A confirmed phone number lets you receive 2FA codes by SMS."
    >
      {step === 'view' && (
        <div className="flex flex-col gap-4">
          {confirmed && (
            <Alert variant="success">Phone number confirmed.</Alert>
          )}
          <div className="flex flex-wrap items-center gap-3 text-sm">
            <span className="font-medium">{profile.phone_number}</span>
            <span className="rounded-full bg-green-100 px-2 py-0.5 text-xs text-green-700">
              Confirmed
            </span>
            <Button
              variant="secondary"
              onClick={() => {
                setConfirmed(false)
                setStep('enter-phone')
              }}
            >
              Change number
            </Button>
          </div>
        </div>
      )}

      {step === 'enter-phone' && (
        <form
          noValidate
          className="flex flex-col gap-4"
          onSubmit={phoneForm.handleSubmit(({ phone_number }) =>
            requestCode.mutate(phone_number),
          )}
        >
          {phoneForm.formState.errors.root && (
            <Alert variant="error">
              {phoneForm.formState.errors.root.message}
            </Alert>
          )}
          <TextField
            label="Phone number"
            type="tel"
            autoComplete="tel"
            placeholder="+380501234567"
            error={phoneForm.formState.errors.phone_number?.message}
            {...phoneForm.register('phone_number')}
          />
          <div className="flex gap-2">
            <Button type="submit" loading={requestCode.isPending}>
              Send code
            </Button>
            {profile.phone_confirmed && (
              <Button
                type="button"
                variant="secondary"
                onClick={() => setStep('view')}
              >
                Cancel
              </Button>
            )}
          </div>
        </form>
      )}

      {step === 'enter-code' && (
        <form
          noValidate
          className="flex flex-col gap-4"
          onSubmit={codeForm.handleSubmit(({ code }) => confirm.mutate(code))}
        >
          <Alert>We sent a code to {pendingPhone}.</Alert>
          {codeForm.formState.errors.root && (
            <Alert variant="error">
              {codeForm.formState.errors.root.message}
            </Alert>
          )}
          <TextField
            label="SMS code"
            inputMode="numeric"
            autoComplete="one-time-code"
            maxLength={6}
            error={codeForm.formState.errors.code?.message}
            {...codeForm.register('code')}
          />
          <div className="flex flex-wrap gap-2">
            <Button type="submit" loading={confirm.isPending}>
              Confirm
            </Button>
            <Button
              type="button"
              variant="secondary"
              loading={requestCode.isPending}
              onClick={() => requestCode.mutate(pendingPhone)}
            >
              Send again
            </Button>
            <Button
              type="button"
              variant="secondary"
              onClick={() => setStep('enter-phone')}
            >
              Use another number
            </Button>
          </div>
        </form>
      )}
    </Card>
  )
}
