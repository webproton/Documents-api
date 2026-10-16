import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation, useQuery } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'
import { useParams } from 'react-router'
import { z } from 'zod'

import { parseApiError } from '@/api/errors'
import { requestsApi, type UploadLinkDetails } from '@/api/requests'
import { Alert } from '@/components/ui/Alert'
import { Button } from '@/components/ui/Button'
import { TextField } from '@/components/ui/TextField'
import {
  DOCUMENT_EXTENSIONS,
  validateDocumentFile,
} from '@/features/documents/documentRules'
import { formatDate } from '@/lib/format'
import { applyApiError } from '@/lib/forms'

// Only the file is required (AnonymousDocumentUploadSerializer)
const uploadSchema = z.object({
  file: z
    .instanceof(FileList)
    .refine((files) => files.length > 0, 'Choose a file')
    .superRefine((files, ctx) => {
      const error = files[0] && validateDocumentFile(files[0])
      if (error) ctx.addIssue({ code: 'custom', message: error })
    }),
  name: z.string().trim().max(255),
  expiration_date: z.string(),
})
type UploadValues = z.infer<typeof uploadSchema>

const closedMessages = {
  COMPLETED: 'A document has already been uploaded with this link. Thank you!',
  CANCELED: 'This request was canceled by the person who sent it.',
  EXPIRED: 'This link has expired. Ask the sender for a new one.',
}

function UploadForm({
  token,
  details,
}: {
  token: string
  details: UploadLinkDetails
}) {
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors },
  } = useForm<UploadValues>({
    resolver: zodResolver(uploadSchema),
    defaultValues: { name: '', expiration_date: '' },
  })

  const upload = useMutation({
    mutationFn: ({ file, name, expiration_date }: UploadValues) =>
      requestsApi.uploadByLink(token, { file: file[0], name, expiration_date }),
    // "token" errors (expired / already used) are about the whole link
    onError: (error) =>
      applyApiError(error, setError, ['file', 'name', 'expiration_date']),
  })

  if (upload.isSuccess) {
    return (
      <Alert variant="success">
        Thank you! Your document was sent to {details.requester_email}. You can
        close this page.
      </Alert>
    )
  }

  const { document_type: type } = details

  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-slate-600">
        <span className="font-medium">{details.requester_email}</span> asks you
        to upload this document. The link works once, until{' '}
        {formatDate(details.expires_at)}. No account is needed.
      </p>
      {type.description && (
        <p className="text-sm text-slate-500">{type.description}</p>
      )}
      {type.template && (
        <a
          href={type.template}
          target="_blank"
          rel="noopener noreferrer"
          className="text-sm font-medium text-blue-600 hover:underline"
        >
          Download the template
        </a>
      )}

      <form
        noValidate
        className="flex flex-col gap-4"
        onSubmit={handleSubmit((values) => upload.mutate(values))}
      >
        {errors.root && <Alert variant="error">{errors.root.message}</Alert>}

        <div className="flex flex-col gap-1">
          <label
            htmlFor="public-upload-file"
            className="text-sm font-medium text-slate-700"
          >
            File
          </label>
          <input
            id="public-upload-file"
            type="file"
            accept={DOCUMENT_EXTENSIONS.join(',')}
            className="text-sm"
            {...register('file')}
          />
          <p className="text-xs text-slate-500">
            PDF, XLS, XLSX or CSV, up to 10 MB.
          </p>
          {errors.file && (
            <p className="text-sm text-red-600">{errors.file.message}</p>
          )}
        </div>
        <TextField
          label="Name (optional)"
          error={errors.name?.message}
          {...register('name')}
        />
        <TextField
          label="Expiration date (optional)"
          type="date"
          error={errors.expiration_date?.message}
          {...register('expiration_date')}
        />

        <Button type="submit" loading={upload.isPending}>
          Upload document
        </Button>
      </form>
    </div>
  )
}

/**
 * Public page behind the emailed link /upload/:token —
 * anyone with the link uploads one document, no login.
 */
export function PublicUploadPage() {
  const token = useParams().token ?? ''
  const details = useQuery({
    queryKey: ['upload-link', token],
    queryFn: () => requestsApi.getUploadLink(token),
    retry: false,
  })

  const notFound =
    details.isError && parseApiError(details.error).status === 404

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-semibold">
        {details.data
          ? `Upload: ${details.data.document_type.name}`
          : 'Upload document'}
      </h1>

      {details.isPending && <p className="text-slate-500">Loading…</p>}
      {notFound && (
        <Alert variant="error">
          This upload link is not valid. Check that you opened the full link
          from the email.
        </Alert>
      )}
      {details.isError && !notFound && (
        <Alert variant="error">{parseApiError(details.error).message}</Alert>
      )}

      {details.data &&
        (details.data.status === 'PENDING' ? (
          <UploadForm token={token} details={details.data} />
        ) : (
          <Alert variant="info">{closedMessages[details.data.status]}</Alert>
        ))}
    </div>
  )
}
