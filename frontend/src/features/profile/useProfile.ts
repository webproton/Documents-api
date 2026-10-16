import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useCallback } from 'react'

import { profileApi } from '@/api/profile'

export const profileQueryKey = ['profile'] as const

/** Current user's profile, shared by the header and profile pages. */
export function useProfile() {
  return useQuery({ queryKey: profileQueryKey, queryFn: profileApi.get })
}

/** Refetch the profile after an update (PATCH returns only changed fields). */
export function useRefreshProfile() {
  const queryClient = useQueryClient()
  return useCallback(
    () => queryClient.invalidateQueries({ queryKey: profileQueryKey }),
    [queryClient],
  )
}
