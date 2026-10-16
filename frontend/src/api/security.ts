import type { TwoFactorMethod } from './auth'
import { apiClient } from './client'

/** A browser/device the user is signed in from (GET /devices/). */
export interface UserDevice {
  id: number
  user_agent: string
  ip_address: string | null
  location: string
  last_login_at: string | null
  /** The browser making this request (matched by X-Device-Token). */
  is_current: boolean
  /** Signed in right now; false after logout on a still-trusted device. */
  is_active_session: boolean
  /** Skips 2FA until trusted_until. */
  is_trusted: boolean
  trusted_until: string | null
}

export interface ToggleTwoFactorRequest {
  enable: boolean
  password: string
  method?: TwoFactorMethod
}

interface MessageResponse {
  message: string
}

export const securityApi = {
  /** Sends an SMS code (in DEBUG the backend logs it instead). */
  requestPhoneConfirmation: (phoneNumber: string) =>
    apiClient
      .post<MessageResponse>('/profile/phone/request-confirmation/', {
        phone_number: phoneNumber,
      })
      .then((res) => res.data),

  confirmPhone: (code: string) =>
    apiClient
      .post<MessageResponse>('/profile/phone/confirm/', { code })
      .then((res) => res.data),

  toggleTwoFactor: (data: ToggleTwoFactorRequest) =>
    apiClient
      .post<MessageResponse>('/profile/2fa/toggle/', data)
      .then((res) => res.data),

  listDevices: () =>
    apiClient.get<UserDevice[]>('/devices/').then((res) => res.data),

  /** Ends the session on that device: its tokens stop working, trust is lost. */
  revokeDevice: (id: number) =>
    apiClient
      .post<MessageResponse>(`/devices/${id}/revoke/`)
      .then((res) => res.data),

  /** Ends every session except the current one. */
  revokeOtherDevices: () =>
    apiClient
      .post<MessageResponse>('/devices/revoke-all/')
      .then((res) => res.data),
}
