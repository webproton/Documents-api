import type { FieldValues, Path, UseFormSetError } from 'react-hook-form'

import { parseApiError } from '@/api/errors'

/**
 * Show an API error in a react-hook-form form.
 *
 * Errors for known fields go under those inputs; everything else
 * (detail, non_field_errors, unknown fields) goes to errors.root.
 */
export function applyApiError<T extends FieldValues>(
  error: unknown,
  setError: UseFormSetError<T>,
  fields: readonly Path<T>[],
): void {
  const { message, fieldErrors } = parseApiError(error)
  let rootMessage: string | null = message

  for (const [field, fieldMessage] of Object.entries(fieldErrors)) {
    if ((fields as readonly string[]).includes(field)) {
      setError(field as Path<T>, { type: 'server', message: fieldMessage })
      // Message is already shown under the field
      if (fieldMessage === rootMessage) rootMessage = null
    }
  }

  if (rootMessage) setError('root', { type: 'server', message: rootMessage })
}
