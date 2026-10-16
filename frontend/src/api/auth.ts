import { apiClient } from './client'

export interface AuthTokens {
  access: string
  refresh: string
}

export type TwoFactorMethod = 'EMAIL' | 'SMS'

/** 200: 2FA disabled or trusted device — tokens issued right away. */
export interface LoginSuccess extends AuthTokens {
  requires_2fa: false
  id: number
  email: string
}

/** 202: 2FA required — continue on the 2FA page with pre_auth_token. */
export interface LoginTwoFactorRequired {
  requires_2fa: true
  pre_auth_token: string
  delivery_method: TwoFactorMethod
  message: string
}

export type LoginResponse = LoginSuccess | LoginTwoFactorRequired

/** Google sign-in: tokens right away; 2FA step if the backend requires it. */
export type GoogleAuthResponse =
  | (AuthTokens & { id: number; email: string; requires_2fa?: false })
  | LoginTwoFactorRequired

/** 2FA verified: tokens + trusted-device token when remember_device was set. */
export interface TwoFactorVerifyResponse extends AuthTokens {
  id: number
  email: string
  device_token?: string
}

export interface TwoFactorVerifyRequest {
  pre_auth_token: string
  code: string
  /** Trust this browser for 90 days (backend default: true). */
  remember_device: boolean
}

export interface Credentials {
  email: string
  password: string
}

interface MessageResponse {
  message: string
}

export const authApi = {
  register: (data: Credentials) =>
    apiClient
      .post<MessageResponse>('/auth/register/', data)
      .then((res) => res.data),

  confirmEmail: (token: string) =>
    apiClient
      .post<MessageResponse>('/auth/confirm-email/', { token })
      .then((res) => res.data),

  login: (data: Credentials) =>
    apiClient.post<LoginResponse>('/auth/login/', data).then((res) => res.data),

  /** Exchange a Google ID token for JWT (creates or links the account). */
  googleAuth: (idToken: string) =>
    apiClient
      .post<GoogleAuthResponse>('/auth/social/google/', { id_token: idToken })
      .then((res) => res.data),

  verifyTwoFactor: (data: TwoFactorVerifyRequest) =>
    apiClient
      .post<TwoFactorVerifyResponse>('/auth/2fa/verify/', data)
      .then((res) => res.data),

  /** New code for the same 2FA session (server cooldown: 60 s). */
  resendTwoFactor: (preAuthToken: string) =>
    apiClient
      .post<MessageResponse>('/auth/2fa/resend/', {
        pre_auth_token: preAuthToken,
      })
      .then((res) => res.data),

  /** Blacklists the refresh token on the server. */
  logout: (refresh: string) =>
    apiClient
      .post<MessageResponse>('/auth/logout/', { refresh })
      .then((res) => res.data),
}
