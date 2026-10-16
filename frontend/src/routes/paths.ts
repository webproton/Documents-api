/**
 * All frontend routes in one place.
 *
 * Some paths are also built by the backend for links in emails and
 * Stripe redirects — keep them in sync with Django:
 * - confirmEmail  ← accounts RegisterSerializer (email confirmation link)
 * - upload        ← DocumentRequest.get_email_context (anonymous upload link)
 * - billingSuccess / billingCancel ← settings.STRIPE_SUCCESS_URL / STRIPE_CANCEL_URL
 */
export const paths = {
  home: '/',

  // Guest pages
  login: '/login',
  register: '/register',
  confirmEmail: '/confirm-email',
  twoFactor: '/2fa',
  upload: '/upload/:token',

  // Authenticated pages
  documents: '/documents',
  folder: '/documents/:folderId',
  documentTypes: '/types',
  requests: '/requests',
  notifications: '/notifications',
  notification: '/notifications/:notificationId',
  billing: '/billing',
  billingSuccess: '/billing/success',
  billingCancel: '/billing/cancel',
  profile: '/profile',
  security: '/security',
} as const
