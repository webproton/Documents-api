import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router'

import { documentsApi, type DocumentType } from '@/api/documents'
import { parseApiError } from '@/api/errors'
import { Alert } from '@/components/ui/Alert'
import { useDebouncedValue } from '@/hooks/useDebouncedValue'

const documentTypesQueryKey = (search: string) =>
  ['document-types', search] as const

function DocumentTypeCard({ type }: { type: DocumentType }) {
  return (
    <li className="flex flex-col gap-2 rounded-xl border border-slate-200 bg-white p-5">
      <h2 className="font-semibold">{type.name}</h2>
      {type.description && (
        <p className="text-sm whitespace-pre-line text-slate-600">
          {type.description}
        </p>
      )}
      {type.template && (
        <a
          href={type.template}
          target="_blank"
          rel="noopener noreferrer"
          className="mt-auto text-sm font-medium text-blue-600 hover:underline"
        >
          Download template
        </a>
      )}
    </li>
  )
}

/** All document types, searchable by name and description. */
export function DocumentTypesPage() {
  // ?search= keeps the query in the URL (shareable, survives reload)
  const [searchParams, setSearchParams] = useSearchParams()
  const [input, setInput] = useState(searchParams.get('search') ?? '')
  const search = useDebouncedValue(input.trim())

  useEffect(() => {
    setSearchParams(search ? { search } : {}, { replace: true })
  }, [search, setSearchParams])

  const types = useQuery({
    queryKey: documentTypesQueryKey(search),
    queryFn: () => documentsApi.listTypes(search),
    // Keep the old list on screen while the next search loads
    placeholderData: keepPreviousData,
  })

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">Document types</h1>
          <p className="mt-1 text-sm text-slate-500">
            Types you can upload and request. Some include a template to fill
            in.
          </p>
        </div>
        <input
          type="search"
          aria-label="Search document types"
          placeholder="Search by name or description"
          value={input}
          onChange={(event) => setInput(event.target.value)}
          className="w-full max-w-xs rounded-md border border-slate-300 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-slate-200"
        />
      </div>

      {types.isPending && <p className="text-slate-500">Loading…</p>}
      {types.isError && (
        <Alert variant="error">{parseApiError(types.error).message}</Alert>
      )}

      {types.data &&
        (types.data.length === 0 ? (
          <p className="text-slate-500">
            {search
              ? `No document types match “${search}”.`
              : 'No document types yet. They are added by an administrator.'}
          </p>
        ) : (
          <ul
            className={`grid gap-4 sm:grid-cols-2 lg:grid-cols-3 ${
              types.isPlaceholderData ? 'opacity-60' : ''
            }`}
          >
            {types.data.map((type) => (
              <DocumentTypeCard key={type.id} type={type} />
            ))}
          </ul>
        ))}
    </div>
  )
}
