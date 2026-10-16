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

const emptyValues: PasswordValues = {
  current_password: '',
  new_password: '',
  confirm_password: '',
}

export function PasswordForm() {
  const {
    register,
    handleSubmit,
    setError,
    reset,
    formState: { errors },
  } = useForm<PasswordValues>({
    resolver: zodResolver(passwordSchema),
    defaultValues: emptyValues,
  })

  const change = useMutation({
    mutationFn: profileApi.changePassword,
    onSuccess: () => reset(emptyValues),
    onError: (error) =>
      applyApiError(error, setError, ['current_password', 'new_password']),
  })

  return (
    <Card title="Change password">
      <form
        noValidate
        className="flex flex-col gap-4"
        onSubmit={handleSubmit(({ current_password, new_password }) =>
          change.mutate({ current_password, new_password }),
        )}
      >
        {errors.root && <Alert variant="error">{errors.root.message}</Alert>}
        {change.isSuccess && <Alert variant="success">Password changed.</Alert>}

        <TextField
          label="Current password"
          type="password"
          autoComplete="current-password"
          error={errors.current_password?.message}
          {...register('current_password')}
        />
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
          <Button type="submit" loading={change.isPending}>
            Change password
          </Button>
        </div>
      </form>
    </Card>
  )
}
