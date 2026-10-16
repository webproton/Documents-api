/**
 * Full-page navigation to another site (e.g. Stripe Checkout).
 * A separate module so tests can mock it — jsdom cannot navigate.
 */
export function redirectTo(url: string): void {
  window.location.assign(url)
}
