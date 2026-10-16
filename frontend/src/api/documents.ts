import { apiClient } from './client'

/** Document type managed by admins (GET /documents/types/). */
export interface DocumentType {
  id: number
  name: string
  description: string
  /** Template file URL (S3) or null. */
  template: string | null
}

/** The newest upload in a folder is ACTIVE, older versions are REPLACED. */
export type DocumentStatus = 'ACTIVE' | 'REPLACED'

export interface FolderDocument {
  id: number
  name: string
  /** Signed S3 URL, valid for a limited time. */
  file: string
  status: DocumentStatus
  /** "YYYY-MM-DD" */
  expiration_date: string | null
  created: string
}

/** A folder = a document type with the user's documents of that type. */
export interface Folder {
  id: number
  name: string
  description: string
  documents: FolderDocument[]
}

export type FolderOrdering =
  'name' | '-name' | 'documents__created' | '-documents__created'

export interface FolderFilters {
  search?: string
  ordering?: FolderOrdering
  expiration_date_from?: string
  expiration_date_to?: string
}

export interface DocumentUpload {
  name: string
  document_type: number
  expiration_date: string
  file: File
}

export interface DocumentUpdate {
  name: string
  expiration_date: string
}

/** Drop empty filters so they are not sent as "?search=" */
const compact = (params: object) =>
  Object.fromEntries(Object.entries(params).filter(([, value]) => value))

export const documentsApi = {
  /** Search matches name and description (DRF SearchFilter). */
  listTypes: (search = '') =>
    apiClient
      .get<DocumentType[]>('/documents/types/', {
        params: search ? { search } : undefined,
      })
      .then((res) => res.data),

  /** Folders with only the ACTIVE document; empty folders are omitted. */
  listFolders: (filters: FolderFilters = {}) =>
    apiClient
      .get<Folder[]>('/documents/folders/', { params: compact(filters) })
      .then((res) => res.data),

  /** One folder with all versions (active and replaced), newest first. */
  getFolder: (
    id: number,
    filters: Pick<
      FolderFilters,
      'expiration_date_from' | 'expiration_date_to'
    > = {},
  ) =>
    apiClient
      .get<Folder>(`/documents/folders/${id}/`, { params: compact(filters) })
      .then((res) => res.data),

  /** multipart/form-data; the previous active document becomes REPLACED. */
  upload: ({ file, document_type, ...fields }: DocumentUpload) => {
    const form = new FormData()
    form.append('file', file)
    form.append('document_type', String(document_type))
    Object.entries(fields).forEach(([key, value]) => form.append(key, value))
    return apiClient
      .post<FolderDocument>('/documents/upload/', form)
      .then((res) => res.data)
  },

  /** Only name and expiration date can be changed. */
  update: (id: number, data: DocumentUpdate) =>
    apiClient
      .patch<FolderDocument>(`/documents/documents/${id}/`, data)
      .then((res) => res.data),

  /** Deleting the active document makes the newest replaced one active. */
  remove: (id: number) => apiClient.delete(`/documents/documents/${id}/`),
}
