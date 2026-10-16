import { z } from 'zod'

// Same format as RequestPhoneConfirmationSerializer (E.164)
export const phoneSchema = z.object({
  phone_number: z
    .string()
    .trim()
    .regex(/^\+\d{9,15}$/, 'Use international format, e.g. +380501234567'),
})

export const phoneCodeSchema = z.object({
  code: z.string().regex(/^\d{6}$/, 'Enter the 6-digit code'),
})

export const twoFactorSettingsSchema = z.object({
  method: z.enum(['EMAIL', 'SMS']),
  password: z.string().min(1, 'Enter your password to confirm'),
})

export type PhoneValues = z.infer<typeof phoneSchema>
export type PhoneCodeValues = z.infer<typeof phoneCodeSchema>
export type TwoFactorSettingsValues = z.infer<typeof twoFactorSettingsSchema>
