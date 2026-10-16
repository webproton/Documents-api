import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation } from '@tanstack/react-query'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { z } from 'zod'

import { documentsApi, type FolderDocument } from '@/api/documents'
import { parseApiError } from '@/api/errors'
import { Alert } from '@/components/ui/Alert'
import { Button } from '@/components/ui/Button'
import { TextField } from '@/components/ui/TextField'
import { formatDateTime } from '@/lib/format'
import { applyApiError } from '@/lib/forms'

import { ExpiryBadge } from './ExpiryBadge'
import { useRefreshDocuments } from './queries'

const editSchema = z.object({
  name: z.string().trim().min(1, 'Enter a name').max(200),
  expiration_date: z.string().min(1, 'Choose an expiration date'),
})
type EditValues = z.infer<typeof editSchema>

function EditForm({
  document,
  onDone,
}: {
  document: FolderDocument
  onDone: () => void
}) {
  const refreshDocuments = useRefreshDocuments()
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors },
  } = useForm<EditValues>({
    resolver: zodResolver(editSchema),
    defaultValues: {
      name: document.name,
      expiration_date: document.expiration_date ?? '',
    },
  })

  const save = useMutation({
    mutationFn: (values: EditValues) =>
      documentsApi.update(document.id, values),
    onSuccess: async () => {
      await refreshDocuments()
      onDone()
    },
    onError: (error) =>
      applyApiError(error, setError, ['name', 'expiration_date']),
  })

  return (
    <form
      noValidate
      className="flex flex-col gap-3"
      onSubmit={handleSubmit((values) => save.mutate(values))}
    >
      {errors.root && <Alert variant="error">{errors.root.message}</Alert>}
      <div className="grid gap-3 sm:grid-cols-2">
        <TextField
          label="Name"
          error={errors.name?.message}
          {...register('name')}
        />
        <TextField
          label="Expiration date"
          type="date"
          error={errors.expiration_date?.message}
          {...register('expiration_date')}
        />
      </div>
      <div className="flex gap-2">
        <Button type="submit" loading={save.isPending}>
          Save
        </Button>
        <Button type="button" variant="secondary" onClick={onDone}>
          Cancel
        </Button>
      </div>
    </form>
  )
}

/** One version in a folder: details, download, edit and delete. */
export function DocumentVersion({ document }: { document: FolderDocument }) {
  const refreshDocuments = useRefreshDocuments()
  const [mode, setMode] = useState<'view' | 'edit' | 'confirm-delete'>('view')
  const isActive = document.status === 'ACTIVE'

  const remove = useMutation({
    mutationFn: () => documentsApi.remove(document.id),
    onSuccess: refreshDocuments,
  })

  return (
    <li className="flex flex-col gap-3 py-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex flex-col gap-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-medium">{document.name}</span>
            <span
              className={`rounded-full px-2 py-0.5 text-xs ${
                isActive
                  ? 'bg-green-100 text-green-700'
                  : 'bg-slate-100 text-slate-600'
              }`}
            >
              {isActive ? 'Active' : 'Replaced'}
            </span>
          </div>
          <p className="text-sm text-slate-500">
            Uploaded {formatDateTime(document.created)} ·{' '}
            <ExpiryBadge date={document.expiration_date} />
          </p>
        </div>

        {mode === 'view' && (
          <div className="flex flex-wrap gap-2">
            <a
              href={document.file}
              target="_blank"
              rel="noopener noreferrer"
              className="rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100"
            >
              Download
            </a>
            <Button variant="secondary" onClick={() => setMode('edit')}>
              Edit
            </Button>
            <Button
              variant="secondary"
              onClick={() => setMode('confirm-delete')}
            >
              Delete
            </Button>
          </div>
        )}
      </div>

      {mode === 'edit' && (
        <EditForm document={document} onDone={() => setMode('view')} />
      )}

      {mode === 'confirm-delete' && (
        <div className="flex flex-col gap-3 rounded-md border border-red-200 bg-red-50 p-3 text-sm">
          <p>
            Delete “{document.name}”?
            {isActive &&
              ' The newest replaced version of this folder will become active.'}
          </p>
          {remove.isError && (
            <Alert variant="error">{parseApiError(remove.error).message}</Alert>
          )}
          <div className="flex gap-2">
            <Button loading={remove.isPending} onClick={() => remove.mutate()}>
              Yes, delete
            </Button>
            <Button variant="secondary" onClick={() => setMode('view')}>
              Cancel
            </Button>
          </div>
        </div>
      )}
    </li>
  )
}
