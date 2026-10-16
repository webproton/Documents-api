import { useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router'

import type { Subscription } from '@/api/billing'
import { Alert } from '@/components/ui/Alert'
import { paths } from '@/routes/paths'

import { billingQueryKeys, useSubscription } from './queries'

/** How often and how long to wait for the Stripe webhook to activate the plan. */
export const ACTIVATION_POLL_MS = 2000
export const MAX_ACTIVATION_POLLS = 15

const isPaidSubscription = (subscription?: Subscription | null) =>
  Number(subscription?.plan.price ?? 0) > 0

/**
 * Stripe redirects here after payment (settings.STRIPE_SUCCESS_URL).
 * The plan is activated by the webhook, so poll until it shows up (~30 s).
 */
export function BillingSuccessPage() {
  const subscription = useSubscription({
    refetchInterval: (query) =>
      isPaidSubscription(query.state.data) ||
      query.state.dataUpdateCount >= MAX_ACTIVATION_POLLS
        ? false
        : ACTIVATION_POLL_MS,
  })
  const queryClient = useQueryClient()
  const active = isPaidSubscription(subscription.data)
  // Reading dataUpdatedAt subscribes to every response: identical data
  // (still FREE) would otherwise not re-render and we'd never give up
  const responses = subscription.dataUpdatedAt
    ? (queryClient.getQueryState(billingQueryKeys.subscription)
        ?.dataUpdateCount ?? 0)
    : 0
  const gaveUp = !active && responses >= MAX_ACTIVATION_POLLS

  return (
    <div className="flex max-w-xl flex-col gap-4">
      <h1 className="text-2xl font-semibold">Payment successful</h1>
      {active ? (
        <Alert variant="success">
          Your {subscription.data?.plan.name} plan is active. Thank you!
        </Alert>
      ) : gaveUp ? (
        <Alert>
          Payment received. Activation is taking longer than usual — check your
          plan again in a minute.
        </Alert>
      ) : (
        <p className="text-slate-600">Activating your plan…</p>
      )}
      <div className="flex gap-4 text-sm font-medium">
        <Link to={paths.billing} className="text-blue-600 hover:underline">
          Plans &amp; billing
        </Link>
        <Link to={paths.documents} className="text-blue-600 hover:underline">
          My documents
        </Link>
      </div>
    </div>
  )
}

/** Stripe redirects here when the user leaves Checkout without paying. */
export function BillingCancelPage() {
  return (
    <div className="flex max-w-xl flex-col gap-4">
      <h1 className="text-2xl font-semibold">Payment canceled</h1>
      <p className="text-slate-600">
        No payment was made and your plan has not changed.
      </p>
      <Link
        to={paths.billing}
        className="text-sm font-medium text-blue-600 hover:underline"
      >
        Back to plans
      </Link>
    </div>
  )
}
