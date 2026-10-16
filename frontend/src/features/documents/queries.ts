import { useQueryClient } from '@tanstack/react-query'
import { useCallback } from 'react'

import type { FolderFilters } from '@/api/documents'

export const documentQueryKeys = {
  types: (search = '') => ['document-types', search] as const,
  folders: (filters: FolderFilters) => ['folders', filters] as const,
  folder: (id: number, filters: object = {}) =>
    ['folder', id, filters] as const,
}

/** After upload/edit/delete: folder list and folder pages are stale. */
export function useRefreshDocuments() {
  const queryClient = useQueryClient()
  return useCallback(
    () =>
      Promise.all([
        queryClient.invalidateQueries({ queryKey: ['folders'] }),
        queryClient.invalidateQueries({ queryKey: ['folder'] }),
      ]),
    [queryClient],
  )
}
