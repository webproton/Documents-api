import { QueryClient } from '@tanstack/react-query'

/** App default: one retry. Tests use createQueryClient(0). */
export function createQueryClient(retry = 1) {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry,
        refetchOnWindowFocus: false,
      },
    },
  })
}
