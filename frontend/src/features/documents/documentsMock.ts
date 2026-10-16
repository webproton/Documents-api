import { http, HttpResponse } from 'msw'

import type { DocumentType, Folder, FolderDocument } from '@/api/documents'
import { api, server } from '@/test/server'

export interface StoredDocument extends FolderDocument {
  document_type: number
}

/** "YYYY-MM-DD" n days from today */
export function dayFromToday(days: number) {
  const date = new Date()
  date.setDate(date.getDate() + days)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
}

export const PASSPORT: DocumentType = {
  id: 1,
  name: 'Passport',
  description: 'Identity document',
  template: null,
}
export const VISA: DocumentType = {
  id: 2,
  name: 'Visa',
  description: 'Travel visa',
  template: null,
}

/** Read text fields and the file name from a raw multipart body. */
function parseMultipart(body: string) {
  const fields: Record<string, string> = {}
  for (const part of body.split(/-{2,}\S+/)) {
    const file = /name="(\w+)"; filename="([^"]+)"/.exec(part)
    if (file) {
      fields[file[1]] = file[2]
      continue
    }
    const field = /name="(\w+)"\r\n\r\n([\s\S]*?)\r\n$/.exec(part)
    if (field) fields[field[1]] = field[2]
  }
  return fields
}

/**
 * In-memory documents backend with the real rules: one ACTIVE document per
 * type, older ones REPLACED, deleting the active one restores the newest
 * replaced; the folder list shows only active documents.
 */
export function mockDocumentsApi({
  types = [PASSPORT, VISA],
  documents: initial = [],
  uploadLimit,
}: {
  types?: DocumentType[]
  documents?: StoredDocument[]
  uploadLimit?: number
} = {}) {
  let documents = [...initial]
  let nextId = 100
  const requests: { method: string; url: string; body?: unknown }[] = []

  const folderOf = (type: DocumentType, docs: StoredDocument[]): Folder => ({
    ...type,
    documents: docs.map((doc) => {
      const { document_type: _type, ...rest } = doc
      return rest
    }),
  })

  const inDateRange = (doc: StoredDocument, params: URLSearchParams) => {
    const from = params.get('expiration_date_from')
    const to = params.get('expiration_date_to')
    const date = doc.expiration_date ?? ''
    return (!from || date >= from) && (!to || date <= to)
  }

  server.use(
    http.get(api('/documents/types/'), () => HttpResponse.json(types)),

    http.get(api('/documents/folders/'), ({ request }) => {
      const params = new URL(request.url).searchParams
      requests.push({ method: 'GET', url: `/folders/?${params}` })
      const search = params.get('search')?.toLowerCase() ?? ''
      const ordering = params.get('ordering') ?? 'name'

      let folders = types
        .map((type) => ({
          type,
          active: documents.filter(
            (doc) =>
              doc.document_type === type.id &&
              doc.status === 'ACTIVE' &&
              inDateRange(doc, params),
          ),
        }))
        .filter(({ active }) => active.length > 0)
        .filter(({ type, active }) =>
          `${type.name} ${active[0].name}`.toLowerCase().includes(search),
        )

      const key = ordering.replace('-', '')
      folders.sort((a, b) =>
        key === 'name'
          ? a.type.name.localeCompare(b.type.name)
          : a.active[0].created.localeCompare(b.active[0].created),
      )
      if (ordering.startsWith('-')) folders = folders.reverse()

      return HttpResponse.json(
        folders.map(({ type, active }) => folderOf(type, active)),
      )
    }),

    http.get(api('/documents/folders/:id/'), ({ params }) => {
      const type = types.find((t) => t.id === Number(params.id))
      if (!type) {
        return HttpResponse.json(
          { status: 'error', errors: { detail: 'Not found.' } },
          { status: 404 },
        )
      }
      const docs = documents
        .filter((doc) => doc.document_type === type.id)
        .sort((a, b) => b.created.localeCompare(a.created))
      return HttpResponse.json(folderOf(type, docs))
    }),

    http.post(api('/documents/upload/'), async ({ request }) => {
      const body = parseMultipart(await request.text())
      requests.push({ method: 'POST', url: '/upload/', body })
      if (uploadLimit !== undefined && documents.length >= uploadLimit) {
        return HttpResponse.json(
          {
            status: 'error',
            errors: {
              document_type: [
                `Document limit reached (${uploadLimit}). Upgrade your plan to upload more documents.`,
              ],
            },
          },
          { status: 400 },
        )
      }
      const typeId = Number(body.document_type)
      documents = documents.map((doc) =>
        doc.document_type === typeId && doc.status === 'ACTIVE'
          ? { ...doc, status: 'REPLACED' }
          : doc,
      )
      const created: StoredDocument = {
        id: nextId++,
        name: body.name,
        file: `https://bucket.s3.amazonaws.com/documents/${body.file}?X-Amz-Signature=x`,
        status: 'ACTIVE',
        expiration_date: body.expiration_date,
        created: new Date().toISOString(),
        document_type: typeId,
      }
      documents.push(created)
      return HttpResponse.json(created, { status: 201 })
    }),

    http.patch(
      api('/documents/documents/:id/'),
      async ({ request, params }) => {
        const body = (await request.json()) as Partial<StoredDocument>
        requests.push({
          method: 'PATCH',
          url: `/documents/${params.id}/`,
          body,
        })
        documents = documents.map((doc) =>
          doc.id === Number(params.id) ? { ...doc, ...body } : doc,
        )
        return HttpResponse.json(
          documents.find((d) => d.id === Number(params.id)),
        )
      },
    ),

    http.delete(api('/documents/documents/:id/'), ({ params }) => {
      requests.push({ method: 'DELETE', url: `/documents/${params.id}/` })
      const doc = documents.find((d) => d.id === Number(params.id))
      documents = documents.filter((d) => d !== doc)
      if (doc?.status === 'ACTIVE') {
        const newest = documents
          .filter((d) => d.document_type === doc.document_type)
          .sort((a, b) => b.created.localeCompare(a.created))[0]
        if (newest) newest.status = 'ACTIVE'
      }
      return new HttpResponse(null, { status: 204 })
    }),
  )

  return { requests, getDocuments: () => documents }
}

export const storedDocument = (
  overrides: Partial<StoredDocument>,
): StoredDocument => ({
  id: 1,
  name: 'My passport',
  file: 'https://bucket.s3.amazonaws.com/documents/passport.pdf?X-Amz-Signature=x',
  status: 'ACTIVE',
  expiration_date: dayFromToday(365),
  created: '2026-01-10T10:00:00Z',
  document_type: PASSPORT.id,
  ...overrides,
})
