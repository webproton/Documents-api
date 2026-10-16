import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useParams } from 'react-router'

import { documentsApi } from '@/api/documents'
import { parseApiError } from '@/api/errors'
import { Alert } from '@/components/ui/Alert'
import { Button } from '@/components/ui/Button'
import { paths } from '@/routes/paths'

import { DocumentVersion } from './DocumentVersion'
import { documentQueryKeys } from './queries'
import { UploadDocumentDialog } from './UploadDocumentDialog'

/** All versions of the user's documents of one type (active + replaced). */
export function FolderPage() {
  const folderId = Number(useParams().folderId)
  const [uploading, setUploading] = useState(false)

  const folder = useQuery({
    queryKey: documentQueryKeys.folder(folderId),
    queryFn: () => documentsApi.getFolder(folderId),
    enabled: Number.isInteger(folderId),
  })

  return (
    <div className="flex max-w-4xl flex-col gap-6">
      <Link
        to={paths.documents}
        className="text-sm text-blue-600 hover:underline"
      >
        ← All documents
      </Link>

      {folder.isPending && <p className="text-slate-500">Loading…</p>}
      {folder.isError && (
        <Alert variant="error">{parseApiError(folder.error).message}</Alert>
      )}

      {folder.data && (
        <>
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <h1 className="text-2xl font-semibold">{folder.data.name}</h1>
              {folder.data.description && (
                <p className="mt-1 text-sm text-slate-500">
                  {folder.data.description}
                </p>
              )}
            </div>
            <Button onClick={() => setUploading(true)}>
              Upload new version
            </Button>
          </div>

          {folder.data.documents.length === 0 ? (
            <p className="text-slate-500">
              No documents in this folder. Upload one to start it.
            </p>
          ) : (
            <section className="rounded-xl border border-slate-200 bg-white px-4 sm:px-6">
              <ul className="divide-y divide-slate-200">
                {folder.data.documents.map((document) => (
                  <DocumentVersion key={document.id} document={document} />
                ))}
              </ul>
            </section>
          )}
        </>
      )}

      {uploading && (
        <UploadDocumentDialog
          documentTypeId={folderId}
          onClose={() => setUploading(false)}
          onUploaded={() => setUploading(false)}
        />
      )}
    </div>
  )
}
