import type { TwoFactorMethod } from './auth'
import { apiClient } from './client'

export interface Profile {
  id: number
  email: string
  first_name: string
  last_name: string
  /** Absolute URL (S3) or null when no avatar is set. */
  avatar: string | null
  is_2fa_enabled: boolean
  two_factor_method: TwoFactorMethod
  phone_number: string | null
  phone_confirmed: boolean
  /** False for Google-created accounts: first password needs no current one. */
  has_password: boolean
}

export interface ProfileNameUpdate {
  first_name: string
  last_name: string
}

export interface PasswordChange {
  /** Required unless the account has no password yet (has_password=false). */
  current_password?: string
  new_password: string
}

/** PATCH /profile/ answers with the updated fields only, not the full Profile. */
type ProfileUpdateResponse = Pick<
  Profile,
  'first_name' | 'last_name' | 'avatar'
>

export const profileApi = {
  get: () => apiClient.get<Profile>('/profile/').then((res) => res.data),

  updateName: (data: ProfileNameUpdate) =>
    apiClient
      .patch<ProfileUpdateResponse>('/profile/', data)
      .then((res) => res.data),

  /** multipart/form-data: JPEG or PNG up to 5 MB (UpdateProfileSerializer). */
  uploadAvatar: (file: File) => {
    const form = new FormData()
    form.append('avatar', file)
    return apiClient
      .patch<ProfileUpdateResponse>('/profile/', form)
      .then((res) => res.data)
  },

  changePassword: (data: PasswordChange) =>
    apiClient
      .patch<ProfileUpdateResponse>('/profile/', data)
      .then((res) => res.data),
}
