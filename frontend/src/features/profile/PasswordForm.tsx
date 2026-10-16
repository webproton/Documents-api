import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'

import { profileApi } from '@/api/profile'
import { Alert } from '@/components/ui/Alert'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { TextField } from '@/components/ui/TextField'
import { applyApiError } from '@/lib/forms'

import { passwordSchema, type PasswordValues } from './schemas'
import { useRefreshProfile } from './useProfile'

const emptyValues: PasswordValues = {
  current_password: '',
  new_password: '',
  confirm_password: '',
}

interface PasswordFormProps {
  /** False for Google-created accounts: "set" instead of "change". */
  hasPassword: boolean
}

export function PasswordForm({ hasPassword }: PasswordFormProps) {
  const refreshProfile = useRefreshProfile()
  const {
    register,
    handleSubmit,
    setError,
    reset,
    formState: { errors },
  } = useForm<PasswordValues>({
    resolver: zodResolver(passwordSchema(hasPassword)),
    defaultValues: emptyValues,
  })

  const save = useMutation({
    mutationFn: profileApi.changePassword,
    onSuccess: () => {
      reset(emptyValues)
      // A first password switches the form to "change" mode
      if (!hasPassword) return refreshProfile()
    },
    onError: (error) =>
      applyApiError(error, setError, ['current_password', 'new_password']),
  })

  const title = hasPassword ? 'Change password' : 'Set password'

  return (
    <Card
      title={title}
      description={
        hasPassword
          ? undefined
          : 'You signed up with Google. Set a password to also log in with your email.'
      }
    >
      <form
        noValidate
        className="flex flex-col gap-4"
        onSubmit={handleSubmit(({ current_password, new_password }) =>
          save.mutate(
            hasPassword ? { current_password, new_password } : { new_password },
          ),
        )}
      >
        {errors.root && <Alert variant="error">{errors.root.message}</Alert>}
        {save.isSuccess && (
          <Alert variant="success">
            {/* Based on what was sent: hasPassword flips to true after a first set */}
            {save.variables.current_password === undefined
              ? 'Password set.'
              : 'Password changed.'}
          </Alert>
        )}

        {hasPassword && (
          <TextField
            label="Current password"
            type="password"
            autoComplete="current-password"
            error={errors.current_password?.message}
            {...register('current_password')}
          />
        )}
        <div className="grid gap-4 sm:grid-cols-2">
          <TextField
            label="New password"
            type="password"
            autoComplete="new-password"
            error={errors.new_password?.message}
            {...register('new_password')}
          />
          <TextField
            label="Confirm new password"
            type="password"
            autoComplete="new-password"
            error={errors.confirm_password?.message}
            {...register('confirm_password')}
          />
        </div>

        <div>
          <Button type="submit" loading={save.isPending}>
            {title}
          </Button>
        </div>
      </form>
    </Card>
  )
}
