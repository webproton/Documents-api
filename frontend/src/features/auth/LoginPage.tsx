import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'
import { Link, useLocation, useNavigate } from 'react-router'

import { authApi } from '@/api/auth'
import { Alert } from '@/components/ui/Alert'
import { Button } from '@/components/ui/Button'
import { TextField } from '@/components/ui/TextField'
import { applyApiError } from '@/lib/forms'
import type { RedirectState } from '@/routes/guards'
import { paths } from '@/routes/paths'

import { useAuth } from './auth-context'
import { loginSchema, type LoginValues } from './schemas'
import type { TwoFactorState } from './two-factor'

export function LoginPage() {
  const { signIn } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors },
  } = useForm<LoginValues>({ resolver: zodResolver(loginSchema) })

  const login = useMutation({
    mutationFn: authApi.login,
    onSuccess: (data) => {
      if (data.requires_2fa) {
        const state: TwoFactorState = {
          preAuthToken: data.pre_auth_token,
          deliveryMethod: data.delivery_method,
          message: data.message,
          // Keep the originally requested page through the 2FA step
          from: (location.state as RedirectState | null)?.from,
        }
        navigate(paths.twoFactor, { state })
        return
      }
      // GuestRoute redirects to the originally requested page
      signIn(data)
    },
    onError: (error) => applyApiError(error, setError, ['email', 'password']),
  })

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-semibold">Log in</h1>

      <form
        noValidate
        className="flex flex-col gap-4"
        onSubmit={handleSubmit((values) => login.mutate(values))}
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
          autoComplete="current-password"
          error={errors.password?.message}
          {...register('password')}
        />

        <Button type="submit" loading={login.isPending}>
          Log in
        </Button>
      </form>

      <p className="text-center text-sm text-slate-600">
        No account?{' '}
        <Link to={paths.register} className="text-blue-600 hover:underline">
          Sign up
        </Link>
      </p>
    </div>
  )
}
