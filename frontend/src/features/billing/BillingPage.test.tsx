import { act, screen, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { Plan, Subscription } from '@/api/billing'
import { redirectTo } from '@/lib/navigation'
import { api, apiError, server } from '@/test/server'
import { renderApp, signInAs } from '@/test/utils'

import { ACTIVATION_POLL_MS, MAX_ACTIVATION_POLLS } from './BillingResultPages'

vi.mock('@/lib/navigation', () => ({ redirectTo: vi.fn() }))

const FREE: Plan = {
  id: 1,
  name: 'FREE',
  description: 'Default plan',
  document_limit: 5,
  price: '0.00',
}
const PRO: Plan = {
  id: 2,
  name: 'PRO',
  description: 'For individuals',
  document_limit: null,
  price: '9.99',
}
const BUSINESS: Plan = {
  id: 3,
  name: 'BUSINESS',
  description: 'For teams',
  document_limit: null,
  price: '29.00',
}

const subscriptionOn = (
  plan: Plan,
  overrides: Partial<Subscription> = {},
): Subscription => ({
  id: 1,
  plan,
  status: 'ACTIVE',
  start_date: '2026-09-16T10:00:00Z',
  end_date: null,
  current_period_end: Number(plan.price) > 0 ? '2026-11-16T10:00:00Z' : null,
  cancel_at_period_end: false,
  created: '2026-09-16T10:00:00Z',
  documents_used: 3,
  ...overrides,
})

/**
 * Billing backend: change-plan returns a Checkout session while there is
 * no paid plan, otherwise switches the plan in place (like the real API).
 */
function mockBillingApi(initial: Subscription | null) {
  let subscription = initial
  const calls: { url: string; body?: unknown }[] = []
  server.use(
    http.get(api('/billing/plans/'), () =>
      HttpResponse.json([FREE, PRO, BUSINESS]),
    ),
    http.get(api('/billing/subscription/'), () =>
      subscription
        ? HttpResponse.json(subscription)
        : new HttpResponse(null, { status: 404 }),
    ),
    http.post(
      api('/billing/subscription/change-plan/'),
      async ({ request }) => {
        const body = (await request.json()) as { plan: number }
        calls.push({ url: '/change-plan/', body })
        const plan = [FREE, PRO, BUSINESS].find((p) => p.id === body.plan)!
        if (!subscription || Number(subscription.plan.price) === 0) {
          return HttpResponse.json({
            checkout_url: 'https://checkout.stripe.com/c/pay/cs_test_123',
            session_id: 'cs_test_123',
          })
        }
        subscription = { ...subscription, plan }
        return HttpResponse.json(subscription)
      },
    ),
    http.post(api('/billing/subscription/cancel/'), () => {
      calls.push({ url: '/cancel/' })
      subscription = subscription && {
        ...subscription,
        cancel_at_period_end: true,
      }
      return HttpResponse.json({
        message:
          'Subscription will be canceled at the end of the current billing period',
      })
    }),
  )
  return {
    calls,
    setSubscription: (next: Subscription) => {
      subscription = next
    },
  }
}

async function openBilling(initial: Subscription | null) {
  const mock = mockBillingApi(initial)
  signInAs()
  const app = renderApp('/billing')
  await screen.findByRole('heading', { name: 'Available plans' })
  await screen.findAllByRole('listitem')
  return { ...mock, ...app }
}

const planCard = (name: string) =>
  within(
    screen
      .getByRole('heading', { name, level: 3 })
      .closest('li') as HTMLElement,
  )

describe('BillingPage', () => {
  beforeEach(() => vi.mocked(redirectTo).mockClear())

  it('shows the current plan with document usage', async () => {
    await openBilling(subscriptionOn(FREE))

    const current = within(
      screen.getByRole('heading', { name: 'Current plan' }).closest('section')!,
    )
    expect(current.getByText('FREE')).toBeInTheDocument()
    expect(current.getByText('3 of 5 documents used')).toBeInTheDocument()
    expect(current.getByRole('progressbar')).toHaveAttribute(
      'aria-valuenow',
      '3',
    )
    // FREE has nothing to cancel
    expect(
      current.queryByRole('button', { name: 'Cancel subscription' }),
    ).not.toBeInTheDocument()
  })

  it('warns when the upload limit is reached', async () => {
    await openBilling(subscriptionOn(FREE, { documents_used: 5 }))

    expect(screen.getByText(/Limit reached/)).toBeInTheDocument()
  })

  it('lists plans with price and limit, marking the current one', async () => {
    await openBilling(subscriptionOn(FREE))

    expect(planCard('FREE').getByText('Your plan')).toBeInTheDocument()
    expect(planCard('PRO').getByText('$9.99 / month')).toBeInTheDocument()
    expect(planCard('PRO').getByText('Unlimited documents')).toBeInTheDocument()
    expect(planCard('FREE').getByText('Up to 5 documents')).toBeInTheDocument()
  })

  it('sends the first payment to Stripe Checkout', async () => {
    const { calls, user } = await openBilling(subscriptionOn(FREE))

    await user.click(
      planCard('PRO').getByRole('button', { name: 'Choose PRO' }),
    )

    await expect
      .poll(() => vi.mocked(redirectTo).mock.calls)
      .toEqual([['https://checkout.stripe.com/c/pay/cs_test_123']])
    expect(calls).toEqual([{ url: '/change-plan/', body: { plan: PRO.id } }])
  })

  it('switches an existing paid plan in place', async () => {
    const { user } = await openBilling(subscriptionOn(PRO))

    await user.click(
      planCard('BUSINESS').getByRole('button', { name: 'Choose BUSINESS' }),
    )

    expect(
      await screen.findByText('Your plan is now BUSINESS.'),
    ).toBeInTheDocument()
    expect(planCard('BUSINESS').getByText('Your plan')).toBeInTheDocument()
    expect(redirectTo).not.toHaveBeenCalled()
  })

  it('shows why a plan cannot be bought', async () => {
    mockBillingApi(subscriptionOn(FREE))
    server.use(
      http.post(api('/billing/subscription/change-plan/'), () =>
        apiError(400, {
          plan: ['Stripe price is not configured for this plan.'],
        }),
      ),
    )
    signInAs()
    const { user } = renderApp('/billing')

    await user.click(await screen.findByRole('button', { name: 'Choose PRO' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Stripe price is not configured for this plan.',
    )
  })

  it('cancels a paid subscription at the end of the period', async () => {
    const { calls, user } = await openBilling(subscriptionOn(PRO))
    expect(screen.getByText('Renews on 16 Nov 2026.')).toBeInTheDocument()

    await user.click(
      screen.getByRole('button', { name: 'Cancel subscription' }),
    )
    await user.click(screen.getByRole('button', { name: 'Yes, cancel' }))

    expect(
      await screen.findByText(/paid features stay until 16 Nov 2026/),
    ).toBeInTheDocument()
    expect(calls).toEqual([{ url: '/cancel/' }])
    expect(
      screen.queryByRole('button', { name: 'Cancel subscription' }),
    ).not.toBeInTheDocument()
  })

  it('handles a user without a subscription', async () => {
    await openBilling(null)

    expect(screen.getByText(/no active subscription/)).toBeInTheDocument()
  })
})

describe('Stripe result pages', () => {
  afterEach(() => vi.useRealTimers())

  it('waits for the webhook to activate the paid plan', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    const { setSubscription } = mockBillingApi(subscriptionOn(FREE))
    signInAs()
    renderApp('/billing/success')

    expect(await screen.findByText('Activating your plan…')).toBeInTheDocument()

    // Webhook processed on the backend
    setSubscription(subscriptionOn(PRO))
    await act(() => vi.advanceTimersByTimeAsync(ACTIVATION_POLL_MS))

    expect(
      await screen.findByText('Your PRO plan is active. Thank you!'),
    ).toBeInTheDocument()
  })

  it('stops waiting after ~30 seconds', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    mockBillingApi(subscriptionOn(FREE))
    signInAs()
    renderApp('/billing/success')
    await screen.findByText('Activating your plan…')

    for (let i = 0; i < MAX_ACTIVATION_POLLS; i++) {
      await act(() => vi.advanceTimersByTimeAsync(ACTIVATION_POLL_MS))
    }

    expect(
      await screen.findByText(/Activation is taking longer than usual/),
    ).toBeInTheDocument()
  })

  it('confirms that nothing was charged after leaving Checkout', async () => {
    signInAs()
    renderApp('/billing/cancel')

    expect(
      await screen.findByText(
        'No payment was made and your plan has not changed.',
      ),
    ).toBeInTheDocument()
  })
})
