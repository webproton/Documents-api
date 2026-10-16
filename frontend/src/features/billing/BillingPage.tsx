import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'

import {
  billingApi,
  isCheckoutSession,
  type Plan,
  type Subscription,
} from '@/api/billing'
import { parseApiError } from '@/api/errors'
import { Alert } from '@/components/ui/Alert'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { formatDate } from '@/lib/format'
import { redirectTo } from '@/lib/navigation'

import {
  billingQueryKeys,
  formatLimit,
  formatPrice,
  usePlans,
  useSubscription,
} from './queries'

const isPaid = (plan: Plan) => Number(plan.price) > 0

function UsageBar({ used, limit }: { used: number; limit: number | null }) {
  if (limit === null) {
    return (
      <p className="text-sm text-slate-600">
        {used} documents uploaded · no limit
      </p>
    )
  }
  const percent = Math.min(100, Math.round((used / limit) * 100))
  const full = used >= limit

  return (
    <div className="flex flex-col gap-1">
      <p className="text-sm text-slate-600">
        {used} of {limit} documents used
      </p>
      <div
        role="progressbar"
        aria-label="Documents used"
        aria-valuenow={used}
        aria-valuemin={0}
        aria-valuemax={limit}
        className="h-2 overflow-hidden rounded-full bg-slate-200"
      >
        <div
          className={`h-full ${full ? 'bg-red-500' : 'bg-slate-900'}`}
          style={{ width: `${percent}%` }}
        />
      </div>
      {full && (
        <p className="text-sm text-red-600">
          Limit reached — upgrade to upload more documents.
        </p>
      )}
    </div>
  )
}

function CurrentPlan({ subscription }: { subscription: Subscription }) {
  const queryClient = useQueryClient()
  const [confirmCancel, setConfirmCancel] = useState(false)
  const { plan } = subscription
  const periodEnd = subscription.current_period_end

  const cancel = useMutation({
    mutationFn: billingApi.cancel,
    onSuccess: () => {
      setConfirmCancel(false)
      return queryClient.invalidateQueries({
        queryKey: billingQueryKeys.subscription,
      })
    },
  })

  return (
    <Card title="Current plan">
      <div className="flex flex-col gap-4">
        <div className="flex flex-wrap items-baseline gap-3">
          <span className="text-xl font-semibold">{plan.name}</span>
          <span className="text-sm text-slate-500">
            {formatPrice(plan.price)}
          </span>
        </div>

        <UsageBar
          used={subscription.documents_used}
          limit={plan.document_limit}
        />

        {isPaid(plan) && periodEnd && (
          <p className="text-sm text-slate-600">
            {subscription.cancel_at_period_end
              ? `Canceled — paid features stay until ${formatDate(periodEnd)}, then you move to FREE.`
              : `Renews on ${formatDate(periodEnd)}.`}
          </p>
        )}

        {cancel.isSuccess && (
          <Alert variant="success">{cancel.data.message}.</Alert>
        )}
        {cancel.isError && (
          <Alert variant="error">{parseApiError(cancel.error).message}</Alert>
        )}

        {isPaid(plan) &&
          !subscription.cancel_at_period_end &&
          (confirmCancel ? (
            <div className="flex flex-col gap-3 rounded-md border border-red-200 bg-red-50 p-3 text-sm">
              <p>
                Cancel the subscription? You keep {plan.name} until the end of
                the paid period.
              </p>
              <div className="flex gap-2">
                <Button
                  loading={cancel.isPending}
                  onClick={() => cancel.mutate()}
                >
                  Yes, cancel
                </Button>
                <Button
                  variant="secondary"
                  onClick={() => setConfirmCancel(false)}
                >
                  Keep plan
                </Button>
              </div>
            </div>
          ) : (
            <div>
              <Button
                variant="secondary"
                onClick={() => setConfirmCancel(true)}
              >
                Cancel subscription
              </Button>
            </div>
          ))}
      </div>
    </Card>
  )
}

function PlanCard({
  plan,
  current,
  onChoose,
  choosing,
}: {
  plan: Plan
  current: boolean
  onChoose: () => void
  choosing: boolean
}) {
  return (
    <li
      className={`flex flex-col gap-3 rounded-xl border bg-white p-5 ${
        current ? 'border-slate-900' : 'border-slate-200'
      }`}
    >
      <div>
        <h3 className="text-lg font-semibold">{plan.name}</h3>
        <p className="text-sm text-slate-500">{formatPrice(plan.price)}</p>
      </div>
      <p className="text-sm font-medium">{formatLimit(plan.document_limit)}</p>
      {plan.description && (
        <p className="text-sm text-slate-600">{plan.description}</p>
      )}
      <div className="mt-auto">
        {current ? (
          <span className="text-sm font-medium text-slate-500">Your plan</span>
        ) : (
          // FREE is the default plan: reached by canceling, not by purchase
          isPaid(plan) && (
            <Button loading={choosing} onClick={onChoose}>
              Choose {plan.name}
            </Button>
          )
        )}
      </div>
    </li>
  )
}

/** Plans and the user's subscription; paid plans go through Stripe. */
export function BillingPage() {
  const queryClient = useQueryClient()
  const plans = usePlans()
  const subscription = useSubscription()

  const changePlan = useMutation({
    mutationFn: billingApi.changePlan,
    onSuccess: (result) => {
      // First payment: continue on Stripe, it returns to /billing/success
      if (isCheckoutSession(result)) {
        redirectTo(result.checkout_url)
        return
      }
      // Existing paid subscription: switched in place
      queryClient.setQueryData(billingQueryKeys.subscription, result)
    },
  })

  const currentPlanId = subscription.data?.plan.id
  const error = plans.error ?? subscription.error

  return (
    <div className="flex max-w-5xl flex-col gap-6">
      <h1 className="text-2xl font-semibold">Plans &amp; billing</h1>

      {error && <Alert variant="error">{parseApiError(error).message}</Alert>}
      {changePlan.isError && (
        <Alert variant="error">{parseApiError(changePlan.error).message}</Alert>
      )}
      {changePlan.isSuccess && !isCheckoutSession(changePlan.data) && (
        <Alert variant="success">
          Your plan is now {changePlan.data.plan.name}.
        </Alert>
      )}

      {subscription.isPending && <p className="text-slate-500">Loading…</p>}
      {subscription.data && <CurrentPlan subscription={subscription.data} />}
      {subscription.data === null && (
        <Alert>You have no active subscription. Choose a plan below.</Alert>
      )}

      <section className="flex flex-col gap-3">
        <h2 className="text-lg font-semibold">Available plans</h2>
        {plans.isPending && <p className="text-slate-500">Loading…</p>}
        {plans.data && (
          <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {plans.data.map((plan) => (
              <PlanCard
                key={plan.id}
                plan={plan}
                current={plan.id === currentPlanId}
                choosing={
                  changePlan.isPending && changePlan.variables === plan.id
                }
                onChoose={() => changePlan.mutate(plan.id)}
              />
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}
