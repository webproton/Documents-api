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

  /** Blacklists the refresh token on the server. */
  logout: (refresh: string) =>
    apiClient
      .post<MessageResponse>('/auth/logout/', { refresh })
      .then((res) => res.data),
}
