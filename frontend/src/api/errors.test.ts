import { AxiosError, AxiosHeaders } from 'axios'
import { describe, expect, it } from 'vitest'

import { parseApiError } from './errors'

function httpError(status: number, data: unknown) {
  const config = { headers: new AxiosHeaders() }
  return new AxiosError('Request failed', 'ERR_BAD_REQUEST', config, null, {
    status,
    statusText: '',
    headers: {},
    config,
    data,
  })
}

describe('parseApiError', () => {
  it('reads field errors from the custom exception handler format', () => {
    const error = httpError(400, {
      status: 'error',
      errors: { email: ['Email already exists'], password: ['Too short'] },
    })

    expect(parseApiError(error)).toEqual({
      status: 400,
      message: 'Email already exists',
      fieldErrors: { email: 'Email already exists', password: 'Too short' },
    })
  })

  it('prefers detail as the general message', () => {
    const error = httpError(401, {
      status: 'error',
      errors: { detail: 'This account has been blocked.', code: 'x' },
    })

    expect(parseApiError(error).message).toBe('This account has been blocked.')
  })

  it('reads non_field_errors', () => {
    const error = httpError(400, {
      status: 'error',
      errors: { non_field_errors: ['Invalid or expired code.'] },
    })

    const result = parseApiError(error)
    expect(result.message).toBe('Invalid or expired code.')
    expect(result.fieldErrors).toEqual({})
  })

  it('reads errors returned directly by a view', () => {
    const error = httpError(400, { error: 'Invalid or expired token' })

    expect(parseApiError(error).message).toBe('Invalid or expired token')
  })

  it('reads a plain list of messages', () => {
    const error = httpError(400, { status: 'error', errors: ['Limit reached'] })

    expect(parseApiError(error).message).toBe('Limit reached')
  })

  it('reports a network error when there is no response', () => {
    const error = new AxiosError('Network Error', 'ERR_NETWORK')

    expect(parseApiError(error)).toEqual({
      status: null,
      message: 'Server is unavailable. Check your connection.',
      fieldErrors: {},
    })
  })

  it('falls back for unknown errors', () => {
    expect(parseApiError(new Error('boom')).message).toBe(
      'Something went wrong. Please try again.',
    )
  })
})
