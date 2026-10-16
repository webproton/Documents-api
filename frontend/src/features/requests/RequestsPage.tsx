import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { generatePath } from 'react-router'
import { useForm } from 'react-hook-form'
import { z } from 'zod'

import { documentsApi } from '@/api/documents'
import { parseApiError } from '@/api/errors'
import { requestsApi, type DocumentRequest } from '@/api/requests'
import { Alert } from '@/components/ui/Alert'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { TextField } from '@/components/ui/TextField'
import { documentQueryKeys } from '@/features/documents/queries'
import { formatDate, formatDateTime } from '@/lib/format'
import { applyApiError } from '@/lib/forms'
import { paths } from '@/routes/paths'

import {
  effectiveStatus,
  nextResendAt,
  statusLabels,
  statusTones,
} from './requestRules'

const requestsQueryKey = ['document-requests'] as const

const createSchema = z.object({
  recipient_email: z.email('Enter a valid email address'),
  document_type: z.string().min(1, 'Choose a document type'),
})
type CreateValues = z.infer<typeof createSchema>

function NewRequestForm() {
  const queryClient = useQueryClient()
  const types = useQuery({
    queryKey: documentQueryKeys.types(),
    queryFn: () => documentsApi.listTypes(),
  })
  const {
    register,
    handleSubmit,
    setError,
    reset,
    formState: { errors },
  } = useForm<CreateValues>({
    resolver: zodResolver(createSchema),
    defaultValues: { recipient_email: '', document_type: '' },
  })

  const create = useMutation({
    mutationFn: (values: CreateValues) =>
      requestsApi.create({
        recipient_email: values.recipient_email,
        document_type: Number(values.document_type),
      }),
    onSuccess: () => {
      reset()
      return queryClient.invalidateQueries({ queryKey: requestsQueryKey })
    },
    onError: (error) =>
      applyApiError(error, setError, ['recipient_email', 'document_type']),
  })

  return (
    <Card
      title="Request a document"
      description="We email a secure link. The recipient uploads one document without an account; it lands in your folder. The link works for 30 days."
    >
      <form
        noValidate
        className="flex flex-col gap-4"
        onSubmit={handleSubmit((values) => create.mutate(values))}
      >
        {errors.root && <Alert variant="error">{errors.root.message}</Alert>}
        {create.isSuccess && (
          <Alert variant="success">
            Request sent to {create.data.recipient_email}.
          </Alert>
        )}

        <div className="grid gap-4 sm:grid-cols-2">
          <TextField
            label="Recipient email"
            type="email"
            error={errors.recipient_email?.message}
            {...register('recipient_email')}
          />
          <div className="flex flex-col gap-1">
            <label
              htmlFor="request-document-type"
              className="text-sm font-medium text-slate-700"
            >
              Document type
            </label>
            <select
              id="request-document-type"
              className="rounded-md border border-slate-300 px-3 py-2 text-sm"
              {...register('document_type')}
            >
              <option value="">
                {types.isPending ? 'Loading…' : 'Choose a type'}
              </option>
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
        </div>

        <div>
          <Button type="submit" loading={create.isPending}>
            Send request
          </Button>
        </div>
      </form>
    </Card>
  )
}

function RequestRow({ request }: { request: DocumentRequest }) {
  const queryClient = useQueryClient()
  const [confirmCancel, setConfirmCancel] = useState(false)
  const [copied, setCopied] = useState(false)
  const status = effectiveStatus(request)
  const resendAt = nextResendAt(request)
  const refresh = () =>
    queryClient.invalidateQueries({ queryKey: requestsQueryKey })

  const resend = useMutation({
    mutationFn: () => requestsApi.resend(request.id),
    onSuccess: refresh,
  })
  const cancel = useMutation({
    mutationFn: () => requestsApi.cancel(request.id),
    onSuccess: refresh,
  })

  const copyLink = async () => {
    const path = generatePath(paths.upload, { token: request.token })
    await navigator.clipboard.writeText(`${window.location.origin}${path}`)
    setCopied(true)
  }

  const actionError = resend.error ?? cancel.error

  return (
    <li className="flex flex-col gap-3 py-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex flex-col gap-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-medium">{request.document_type_name}</span>
            <span
              className={`rounded-full px-2 py-0.5 text-xs ${statusTones[status]}`}
            >
              {statusLabels[status]}
            </span>
          </div>
          <p className="text-sm text-slate-500">
            To {request.recipient_email} · Requested{' '}
            {formatDateTime(request.created)}
            {status === 'PENDING' &&
              ` · Link valid until ${formatDate(request.expires_at)}`}
          </p>
        </div>

        {status === 'PENDING' && !confirmCancel && (
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" onClick={copyLink}>
              {copied ? 'Copied' : 'Copy link'}
            </Button>
            <Button
              variant="secondary"
              disabled={Boolean(resendAt)}
              loading={resend.isPending}
              title={
                resendAt
                  ? `Can be resent at ${formatDateTime(resendAt.toISOString())}`
                  : undefined
              }
              onClick={() => resend.mutate()}
            >
              Resend email
            </Button>
            <Button variant="secondary" onClick={() => setConfirmCancel(true)}>
              Cancel request
            </Button>
          </div>
        )}
      </div>

      {status === 'PENDING' && resendAt && (
        <p className="text-xs text-slate-500">
          Email can be resent after {formatDateTime(resendAt.toISOString())}.
        </p>
      )}
      {resend.isSuccess && (
        <Alert variant="success">{resend.data.detail}</Alert>
      )}
      {actionError && (
        <Alert variant="error">{parseApiError(actionError).message}</Alert>
      )}

      {confirmCancel && status === 'PENDING' && (
        <div className="flex flex-col gap-3 rounded-md border border-red-200 bg-red-50 p-3 text-sm">
          <p>Cancel this request? The upload link will stop working.</p>
          <div className="flex gap-2">
            <Button loading={cancel.isPending} onClick={() => cancel.mutate()}>
              Yes, cancel it
            </Button>
            <Button variant="secondary" onClick={() => setConfirmCancel(false)}>
              Keep it
            </Button>
          </div>
        </div>
      )}
    </li>
  )
}

/** Outgoing document requests: create, track, resend, cancel. */
export function RequestsPage() {
  const requests = useQuery({
    queryKey: requestsQueryKey,
    queryFn: requestsApi.list,
  })

  return (
    <div className="flex max-w-4xl flex-col gap-6">
      <h1 className="text-2xl font-semibold">Document requests</h1>
      <NewRequestForm />

      <Card title="Sent requests">
        {requests.isPending && (
          <p className="text-sm text-slate-500">Loading…</p>
        )}
        {requests.isError && (
          <Alert variant="error">{parseApiError(requests.error).message}</Alert>
        )}
        {requests.data &&
          (requests.data.length === 0 ? (
            <p className="text-sm text-slate-500">No requests sent yet.</p>
          ) : (
            <ul className="divide-y divide-slate-200">
              {requests.data.map((request) => (
                <RequestRow key={request.id} request={request} />
              ))}
            </ul>
          ))}
      </Card>
    </div>
  )
}
