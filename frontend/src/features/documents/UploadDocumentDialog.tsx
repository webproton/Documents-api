import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation, useQuery } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'
import { Link } from 'react-router'
import { z } from 'zod'

import { documentsApi, type FolderDocument } from '@/api/documents'
import { parseApiError } from '@/api/errors'
import { Alert } from '@/components/ui/Alert'
import { Button } from '@/components/ui/Button'
import { Modal } from '@/components/ui/Modal'
import { TextField } from '@/components/ui/TextField'
import { applyApiError } from '@/lib/forms'
import { paths } from '@/routes/paths'

import {
  DOCUMENT_EXTENSIONS,
  isDocumentLimitError,
  validateDocumentFile,
} from './documentRules'
import { documentQueryKeys, useRefreshDocuments } from './queries'

// All four fields are required by the spec (the model allows no expiry date)
const uploadSchema = z.object({
  document_type: z.string().min(1, 'Choose a document type'),
  name: z.string().trim().min(1, 'Enter a name').max(200),
  expiration_date: z.string().min(1, 'Choose an expiration date'),
  file: z
    .instanceof(FileList)
    .refine((files) => files.length > 0, 'Choose a file')
    .superRefine((files, ctx) => {
      const error = files[0] && validateDocumentFile(files[0])
      if (error) ctx.addIssue({ code: 'custom', message: error })
    }),
})

type UploadValues = z.infer<typeof uploadSchema>

interface UploadDocumentDialogProps {
  onClose: () => void
  onUploaded: (document: FolderDocument) => void
  /** Preselect the type when uploading a new version from a folder. */
  documentTypeId?: number
}

export function UploadDocumentDialog({
  onClose,
  onUploaded,
  documentTypeId,
}: UploadDocumentDialogProps) {
  const refreshDocuments = useRefreshDocuments()
  const types = useQuery({
    queryKey: documentQueryKeys.types(),
    queryFn: () => documentsApi.listTypes(),
  })

  const {
    register,
    handleSubmit,
    setError,
    setValue,
    getValues,
    formState: { errors },
  } = useForm<UploadValues>({
    resolver: zodResolver(uploadSchema),
    defaultValues: {
      document_type: documentTypeId ? String(documentTypeId) : '',
      name: '',
      expiration_date: '',
    },
  })

  const upload = useMutation({
    mutationFn: documentsApi.upload,
    onSuccess: async (document) => {
      await refreshDocuments()
      onUploaded(document)
    },
    onError: (error) => {
      // The plan limit comes back as a document_type error: show it with a CTA
      if (isDocumentLimitError(parseApiError(error).message)) return
      applyApiError(error, setError, [
        'document_type',
        'name',
        'expiration_date',
        'file',
      ])
    },
  })

  const limitReached =
    upload.isError && isDocumentLimitError(parseApiError(upload.error).message)

  const fileField = register('file')

  return (
    <Modal title="Upload document" onClose={onClose}>
      {/* Wait for the types so a preselected type shows as selected */}
      {types.isPending && <p className="text-sm text-slate-500">Loading…</p>}
      {types.isError && (
        <Alert variant="error">{parseApiError(types.error).message}</Alert>
      )}
      {types.data && (
        <form
          noValidate
          className="flex flex-col gap-4"
          onSubmit={handleSubmit(({ document_type, file, ...values }) =>
            upload.mutate({
              ...values,
              document_type: Number(document_type),
              file: file[0],
            }),
          )}
        >
          {limitReached && (
            <Alert variant="error">
              {parseApiError(upload.error).message}{' '}
              <Link to={paths.billing} className="font-medium underline">
                See plans
              </Link>
            </Alert>
          )}
          {errors.root && <Alert variant="error">{errors.root.message}</Alert>}

          <div className="flex flex-col gap-1">
            <label
              htmlFor="upload-document-type"
              className="text-sm font-medium text-slate-700"
            >
              Document type
            </label>
            <select
              id="upload-document-type"
              className="rounded-md border border-slate-300 px-3 py-2 text-sm"
              {...register('document_type')}
            >
              <option value="">Choose a type</option>
              {types.data?.map((type) => (
                <option key={type.id} value={type.id}>
                  {type.name}
                </option>
              ))}
            </select>
            {errors.document_type && (
              <p className="text-sm text-red-600">
                {errors.document_type.message}
              </p>
            )}
          </div>

          <div className="flex flex-col gap-1">
            <label
              htmlFor="upload-file"
              className="text-sm font-medium text-slate-700"
            >
              File
            </label>
            <input
              id="upload-file"
              type="file"
              accept={DOCUMENT_EXTENSIONS.join(',')}
              className="text-sm"
              {...fileField}
              onChange={(event) => {
                fileField.onChange(event)
                // Suggest the file name as the document name
                const file = event.target.files?.[0]
                if (file && !getValues('name')) {
                  setValue('name', file.name.replace(/\.[^.]+$/, ''))
                }
              }}
            />
            <p className="text-xs text-slate-500">
              PDF, XLS, XLSX or CSV, up to 10 MB.
            </p>
            {errors.file && (
              <p className="text-sm text-red-600">{errors.file.message}</p>
            )}
          </div>

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

          <div className="flex justify-end gap-2">
            <Button type="button" variant="secondary" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" loading={upload.isPending}>
              Upload
            </Button>
          </div>
        </form>
      )}
    </Modal>
  )
}
