import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'
import { Link } from 'react-router'

import { authApi } from '@/api/auth'
import { Alert } from '@/components/ui/Alert'
import { Button } from '@/components/ui/Button'
import { TextField } from '@/components/ui/TextField'
import { applyApiError } from '@/lib/forms'
import { paths } from '@/routes/paths'

import { GoogleAuthSection } from './GoogleAuthSection'
import { registerSchema, type RegisterValues } from './schemas'

export function RegisterPage() {
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors },
  } = useForm<RegisterValues>({ resolver: zodResolver(registerSchema) })

  const signUp = useMutation({
    mutationFn: authApi.register,
    onError: (error) => applyApiError(error, setError, ['email', 'password']),
  })

  if (signUp.isSuccess) {
    return (
      <div className="flex flex-col gap-4 text-center">
        <h1 className="text-2xl font-semibold">Check your email</h1>
        <p className="text-slate-600">
          We sent a confirmation link to{' '}
          <span className="font-medium">{signUp.variables.email}</span>. Open it
          to activate your account.
        </p>
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
      <h1 className="text-2xl font-semibold">Sign up</h1>

      <form
        noValidate
        className="flex flex-col gap-4"
        onSubmit={handleSubmit(({ email, password }) =>
          signUp.mutate({ email, password }),
        )}
      >
        {errors.root && <Alert variant="error">{errors.root.message}</Alert>}

        <TextField
          label="Email"
          type="email"
          autoComplete="email"
          error={errors.email?.message}
          {...register('email')}
        />
        <TextField
          label="Password"
          type="password"
          autoComplete="new-password"
          error={errors.password?.message}
          {...register('password')}
        />
        <TextField
          label="Confirm password"
          type="password"
          autoComplete="new-password"
          error={errors.confirmPassword?.message}
          {...register('confirmPassword')}
        />

        <Button type="submit" loading={signUp.isPending}>
          Create account
        </Button>
      </form>

      <GoogleAuthSection text="signup_with" />

      <p className="text-center text-sm text-slate-600">
        Already have an account?{' '}
        <Link to={paths.login} className="text-blue-600 hover:underline">
          Log in
        </Link>
      </p>
    </div>
  )
}
