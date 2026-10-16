import { z } from 'zod'

// Mirrors UpdateProfileSerializer: names are optional to send,
// but must not be blank (allow_blank=False, max_length=150)
const name = (label: string) =>
  z
    .string()
    .trim()
    .min(1, `${label} cannot be empty`)
    .max(150, `${label} must be at most 150 characters`)

export const nameSchema = z.object({
  first_name: name('First name'),
  last_name: name('Last name'),
})

/** Current password is required only when the account already has one. */
export const passwordSchema = (hasPassword: boolean) =>
  z
    .object({
      current_password: hasPassword
        ? z.string().min(1, 'Enter your current password')
        : z.string(),
      new_password: z.string().min(8, 'Password must be at least 8 characters'),
      confirm_password: z.string(),
    })
    .refine((data) => data.new_password === data.confirm_password, {
      message: 'Passwords do not match',
      path: ['confirm_password'],
    })

export type NameValues = z.infer<typeof nameSchema>
export type PasswordValues = z.infer<ReturnType<typeof passwordSchema>>

// settings.AVATAR_MAX_SIZE and settings.ALLOWED_AVATAR_TYPES
export const AVATAR_MAX_BYTES = 5 * 1024 * 1024
export const AVATAR_TYPES = ['image/jpeg', 'image/png']

/** Client-side avatar check; returns an error message or null. */
export function validateAvatar(file: File): string | null {
  if (!AVATAR_TYPES.includes(file.type)) return 'Only JPEG and PNG are allowed'
  if (file.size > AVATAR_MAX_BYTES) return 'Max size 5MB'
  return null
}
