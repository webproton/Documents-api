import { QueryClientProvider, type QueryClient } from '@tanstack/react-query'
import { useState, type ReactNode } from 'react'

import { AuthProvider } from '@/features/auth/AuthProvider'
import { createQueryClient } from '@/lib/queryClient'

interface AppProvidersProps {
  children: ReactNode
  /** Tests pass a client without retries; the app creates its own. */
  queryClient?: QueryClient
}

/** Global providers shared by the app and tests. */
export function AppProviders({
  children,
  queryClient: providedClient,
}: AppProvidersProps) {
  // One client per mounted tree (tests get an isolated cache)
  const [queryClient] = useState(() => providedClient ?? createQueryClient())

  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>{children}</AuthProvider>
    </QueryClientProvider>
  )
}
