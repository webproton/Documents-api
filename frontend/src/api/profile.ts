import type { TwoFactorMethod } from './auth'
import { apiClient } from './client'

export interface Profile {
  id: number
  email: string
  first_name: string
  last_name: string
  avatar: string | null
  is_2fa_enabled: boolean
  two_factor_method: TwoFactorMethod
  phone_number: string | null
  phone_confirmed: boolean
}

export const profileApi = {
  get: () => apiClient.get<Profile>('/profile/').then((res) => res.data),
}
