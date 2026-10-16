import { z } from 'zod'

// Client-side checks mirror RegisterSerializer (email, min_length=8);
// the remaining Django password validators run on the server.
const email = z.email('Enter a valid email address')

export const loginSchema = z.object({
  email,
  password: z.string().min(1, 'Enter your password'),
})

export const registerSchema = z
  .object({
    email,
    password: z.string().min(8, 'Password must be at least 8 characters'),
    confirmPassword: z.string(),
  })
  .refine((data) => data.password === data.confirmPassword, {
    message: 'Passwords do not match',
    path: ['confirmPassword'],
  })

// Same rule as TwoFactorVerifySerializer.validate_code
export const twoFactorSchema = z.object({
  code: z.string().regex(/^\d{6}$/, 'Enter the 6-digit code'),
  rememberDevice: z.boolean(),
})

export type LoginValues = z.infer<typeof loginSchema>
export type RegisterValues = z.infer<typeof registerSchema>
export type TwoFactorValues = z.infer<typeof twoFactorSchema>
