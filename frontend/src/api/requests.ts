import { apiClient } from './client'
import type { DocumentType, FolderDocument } from './documents'

export type RequestStatus = 'PENDING' | 'COMPLETED' | 'CANCELED' | 'EXPIRED'

/** An outgoing request: "please upload <type>" sent to an email. */
export interface DocumentRequest {
  id: number
  recipient_email: string
  document_type: number
  document_type_name: string
  /** Secret part of the upload link /upload/<token>. */
  token: string
  status: RequestStatus
  created: string
  expires_at: string
  last_sent_at: string | null
}

export interface DocumentRequestCreate {
  recipient_email: string
  document_type: number
}

/** What the recipient sees before uploading (public, by token). */
export interface UploadLinkDetails {
  document_type: DocumentType
  requester_email: string
  /** EXPIRED as soon as expires_at has passed. */
  status: RequestStatus
  expires_at: string
}

export interface UploadByLink {
  file: File
  name?: string
  expiration_date?: string
}

interface DetailResponse {
  detail: string
}

export const requestsApi = {
  list: () =>
    apiClient
      .get<DocumentRequest[]>('/documents/requests/')
      .then((res) => res.data),

  /** Creates the request and emails the upload link to the recipient. */
  create: (data: DocumentRequestCreate) =>
    apiClient
      .post<DocumentRequest>('/documents/requests/', data)
      .then((res) => res.data),

  /** Sends the email again — at most once per hour. */
  resend: (id: number) =>
    apiClient
      .post<DetailResponse>(`/documents/requests/${id}/resend/`)
      .then((res) => res.data),

  cancel: (id: number) =>
    apiClient
      .post<DetailResponse>(`/documents/requests/${id}/cancel/`)
      .then((res) => res.data),

  // Public: no account needed, the token is the authorization

  getUploadLink: (token: string) =>
    apiClient
      .get<UploadLinkDetails>(`/documents/upload/${token}/`)
      .then((res) => res.data),

  /** Uploads into the requester's folder and closes the request. */
  uploadByLink: (token: string, { file, ...fields }: UploadByLink) => {
    const form = new FormData()
    form.append('file', file)
    Object.entries(fields).forEach(
      ([key, value]) => value && form.append(key, value),
    )
    return apiClient
      .post<FolderDocument>(`/documents/upload/${token}/`, form)
      .then((res) => res.data)
  },
}
