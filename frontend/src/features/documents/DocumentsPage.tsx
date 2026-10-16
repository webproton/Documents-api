import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { generatePath, Link, useSearchParams } from 'react-router'

import {
  documentsApi,
  type Folder,
  type FolderFilters,
  type FolderOrdering,
} from '@/api/documents'
import { parseApiError } from '@/api/errors'
import { Alert } from '@/components/ui/Alert'
import { Button } from '@/components/ui/Button'
import { useDebouncedValue } from '@/hooks/useDebouncedValue'
import { paths } from '@/routes/paths'

import { ExpiryBadge } from './ExpiryBadge'
import { documentQueryKeys } from './queries'
import { UploadDocumentDialog } from './UploadDocumentDialog'

const orderingOptions: { value: FolderOrdering; label: string }[] = [
  { value: 'name', label: 'Type (A–Z)' },
  { value: '-name', label: 'Type (Z–A)' },
  { value: '-documents__created', label: 'Newest first' },
  { value: 'documents__created', label: 'Oldest first' },
]

/** Set or remove one query param, keeping the others. */
function withParam(params: URLSearchParams, key: string, value: string) {
  if (value) params.set(key, value)
  else params.delete(key)
  return params
}

const inputClass =
  'rounded-md border border-slate-300 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-slate-200'

function FolderCard({ folder }: { folder: Folder }) {
  // The list endpoint returns only the active document of each folder
  const active = folder.documents[0]

  return (
    <li className="flex flex-col gap-3 rounded-xl border border-slate-200 bg-white p-5">
      <div>
        <p className="text-xs font-medium tracking-wide text-slate-400 uppercase">
          {folder.name}
        </p>
        <h2 className="mt-1 font-semibold">{active?.name}</h2>
      </div>
      {active && (
        <p className="text-sm text-slate-600">
          <ExpiryBadge date={active.expiration_date} />
        </p>
      )}
      <div className="mt-auto flex flex-wrap gap-3 text-sm font-medium">
        <Link
          to={generatePath(paths.folder, { folderId: String(folder.id) })}
          className="text-blue-600 hover:underline"
        >
          Open folder
        </Link>
        {active && (
          <a
            href={active.file}
            target="_blank"
            rel="noopener noreferrer"
            className="text-blue-600 hover:underline"
          >
            Download
          </a>
        )}
      </div>
    </li>
  )
}

/** The user's folders (one per document type) showing the active document. */
export function DocumentsPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [searchInput, setSearchInput] = useState(
    searchParams.get('search') ?? '',
  )
  const [uploading, setUploading] = useState(false)
  const [uploadedName, setUploadedName] = useState<string | null>(null)
  const search = useDebouncedValue(searchInput.trim())

  // Filters live in the URL: shareable and kept on reload / back
  const filters: FolderFilters = {
    search,
    ordering: (searchParams.get('ordering') as FolderOrdering) || 'name',
    expiration_date_from: searchParams.get('expires_from') ?? '',
    expiration_date_to: searchParams.get('expires_to') ?? '',
  }

  const updateParam = (key: string, value: string) =>
    setSearchParams((params) => withParam(params, key, value), {
      replace: true,
    })

  // Debounced search → URL
  useEffect(() => {
    setSearchParams((params) => withParam(params, 'search', search), {
      replace: true,
    })
  }, [search, setSearchParams])

  const folders = useQuery({
    queryKey: documentQueryKeys.folders(filters),
    queryFn: () => documentsApi.listFolders(filters),
    placeholderData: keepPreviousData,
  })

  const hasFilters = Boolean(
    search || filters.expiration_date_from || filters.expiration_date_to,
  )

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">My documents</h1>
          <p className="mt-1 text-sm text-slate-500">
            One folder per document type. A new upload replaces the active
            document; older versions stay in the folder.
          </p>
        </div>
        <Button onClick={() => setUploading(true)}>Upload document</Button>
      </div>

      {uploadedName && (
        <Alert variant="success">“{uploadedName}” uploaded.</Alert>
      )}

      <div className="flex flex-wrap items-end gap-3">
        <input
          type="search"
          aria-label="Search documents"
          placeholder="Search by name or type"
          value={searchInput}
          onChange={(event) => setSearchInput(event.target.value)}
          className={`${inputClass} w-full max-w-xs`}
        />
        <label className="flex flex-col gap-1 text-xs text-slate-500">
          Sort by
          <select
            value={filters.ordering}
            onChange={(event) => updateParam('ordering', event.target.value)}
            className={inputClass}
          >
            {orderingOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-xs text-slate-500">
          Expires from
          <input
            type="date"
            value={filters.expiration_date_from}
            onChange={(event) =>
              updateParam('expires_from', event.target.value)
            }
            className={inputClass}
          />
        </label>
        <label className="flex flex-col gap-1 text-xs text-slate-500">
          Expires to
          <input
            type="date"
            value={filters.expiration_date_to}
            onChange={(event) => updateParam('expires_to', event.target.value)}
            className={inputClass}
          />
        </label>
      </div>

      {folders.isPending && <p className="text-slate-500">Loading…</p>}
      {folders.isError && (
        <Alert variant="error">{parseApiError(folders.error).message}</Alert>
      )}
      {folders.data &&
        (folders.data.length === 0 ? (
          <p className="text-slate-500">
            {hasFilters
              ? 'No documents match these filters.'
              : 'No documents yet. Upload your first one.'}
          </p>
        ) : (
          <ul
            className={`grid gap-4 sm:grid-cols-2 lg:grid-cols-3 ${
              folders.isPlaceholderData ? 'opacity-60' : ''
            }`}
          >
            {folders.data.map((folder) => (
              <FolderCard key={folder.id} folder={folder} />
            ))}
          </ul>
        ))}

      {uploading && (
        <UploadDocumentDialog
          onClose={() => setUploading(false)}
          onUploaded={(document) => {
            setUploading(false)
            setUploadedName(document.name)
          }}
        />
      )}
    </div>
  )
}
