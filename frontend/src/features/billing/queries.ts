import { useQuery, type UseQueryOptions } from '@tanstack/react-query'

import { billingApi, type Subscription } from '@/api/billing'

export const billingQueryKeys = {
  plans: ['plans'] as const,
  subscription: ['subscription'] as const,
}

export function usePlans() {
  return useQuery({
    queryKey: billingQueryKeys.plans,
    queryFn: billingApi.listPlans,
  })
}

type SubscriptionQueryOptions = Pick<
  UseQueryOptions<Subscription | null>,
  'refetchInterval'
>

export function useSubscription(options: SubscriptionQueryOptions = {}) {
  return useQuery({
    queryKey: billingQueryKeys.subscription,
    queryFn: billingApi.getSubscription,
    ...options,
  })
}

// Mirrors settings.DEFAULT_CURRENCY
const priceFormat = new Intl.NumberFormat('en-US', {
  style: 'currency',
  currency: 'USD',
})

export function formatPrice(price: string): string {
  return Number(price) === 0
    ? 'Free'
    : `${priceFormat.format(Number(price))} / month`
}

export function formatLimit(limit: number | null): string {
  return limit === null ? 'Unlimited documents' : `Up to ${limit} documents`
}
