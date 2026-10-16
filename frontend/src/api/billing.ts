import { isAxiosError } from 'axios'

import { apiClient } from './client'

export interface Plan {
  id: number
  name: string
  description: string
  /** null = unlimited uploads */
  document_limit: number | null
  /** Decimal string, e.g. "9.99" (settings.DEFAULT_CURRENCY) */
  price: string
}

export type SubscriptionStatus =
  'PENDING' | 'ACTIVE' | 'CANCELED' | 'EXPIRED' | 'FAILED'

export interface Subscription {
  id: number
  plan: Plan
  status: SubscriptionStatus
  start_date: string | null
  end_date: string | null
  current_period_end: string | null
  /** Canceled in Stripe, paid features last until current_period_end. */
  cancel_at_period_end: boolean
  created: string
  /** All uploads count towards the limit, replaced versions too. */
  documents_used: number
}

export interface CheckoutSession {
  checkout_url: string
  session_id: string
}

/** First purchase → Stripe Checkout; existing paid plan → changed in place. */
export type ChangePlanResult = CheckoutSession | Subscription

export const isCheckoutSession = (
  result: ChangePlanResult,
): result is CheckoutSession => 'checkout_url' in result

export const billingApi = {
  listPlans: () =>
    apiClient.get<Plan[]>('/billing/plans/').then((res) => res.data),

  /** null when the user has no active subscription (the API answers 404). */
  getSubscription: () =>
    apiClient
      .get<Subscription>('/billing/subscription/')
      .then((res) => res.data)
      .catch((error: unknown) => {
        if (isAxiosError(error) && error.response?.status === 404) return null
        throw error
      }),

  changePlan: (planId: number) =>
    apiClient
      .post<ChangePlanResult>('/billing/subscription/change-plan/', {
        plan: planId,
      })
      .then((res) => res.data),

  /** Cancels at the end of the current billing period. */
  cancel: () =>
    apiClient
      .post<{ message: string }>('/billing/subscription/cancel/')
      .then((res) => res.data),
}
