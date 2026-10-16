import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'

import { profileApi, type Profile } from '@/api/profile'
import { Alert } from '@/components/ui/Alert'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { TextField } from '@/components/ui/TextField'
import { applyApiError } from '@/lib/forms'

import { nameSchema, type NameValues } from './schemas'
import { useRefreshProfile } from './useProfile'

export function NameForm({ profile }: { profile: Profile }) {
  const refreshProfile = useRefreshProfile()
  const {
    register,
    handleSubmit,
    setError,
    reset,
    formState: { errors, isDirty },
  } = useForm<NameValues>({
    resolver: zodResolver(nameSchema),
    defaultValues: {
      first_name: profile.first_name,
      last_name: profile.last_name,
    },
  })

  const save = useMutation({
    mutationFn: profileApi.updateName,
    onSuccess: (data) => {
      // Saved values become the new baseline for isDirty
      reset({ first_name: data.first_name, last_name: data.last_name })
      return refreshProfile()
    },
    onError: (error) =>
      applyApiError(error, setError, ['first_name', 'last_name']),
  })

  return (
    <Card title="Personal information">
      <form
        noValidate
        className="flex flex-col gap-4"
        onSubmit={handleSubmit((values) => save.mutate(values))}
      >
        {errors.root && <Alert variant="error">{errors.root.message}</Alert>}
        {save.isSuccess && !isDirty && (
          <Alert variant="success">Profile updated.</Alert>
        )}

        <TextField label="Email" value={profile.email} disabled readOnly />
        <div className="grid gap-4 sm:grid-cols-2">
          <TextField
            label="First name"
            autoComplete="given-name"
            error={errors.first_name?.message}
            {...register('first_name')}
          />
          <TextField
            label="Last name"
            autoComplete="family-name"
            error={errors.last_name?.message}
            {...register('last_name')}
          />
        </div>

        <div>
          <Button type="submit" loading={save.isPending} disabled={!isDirty}>
            Save changes
          </Button>
        </div>
      </form>
    </Card>
  )
}
