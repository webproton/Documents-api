import { apiClient } from './client'

/** Document type managed by admins (GET /documents/types/). */
export interface DocumentType {
  id: number
  name: string
  description: string
  /** Template file URL (S3) or null. */
  template: string | null
}

export const documentsApi = {
  /** Search matches name and description (DRF SearchFilter). */
  listTypes: (search = '') =>
    apiClient
      .get<DocumentType[]>('/documents/types/', {
        params: search ? { search } : undefined,
      })
      .then((res) => res.data),
}
