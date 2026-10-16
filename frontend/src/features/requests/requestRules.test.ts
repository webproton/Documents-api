import { describe, expect, it } from 'vitest'

import { effectiveStatus, nextResendAt } from './requestRules'

const now = new Date('2026-10-16T12:00:00Z')

describe('effectiveStatus', () => {
  it('treats a pending request past its deadline as expired', () => {
    expect(
      effectiveStatus(
        { status: 'PENDING', expires_at: '2026-10-16T11:59:00Z' },
        now,
      ),
    ).toBe('EXPIRED')
    expect(
      effectiveStatus(
        { status: 'PENDING', expires_at: '2026-10-17T00:00:00Z' },
        now,
      ),
    ).toBe('PENDING')
  })

  it('keeps final statuses as they are', () => {
    expect(
      effectiveStatus(
        { status: 'COMPLETED', expires_at: '2020-01-01T00:00:00Z' },
        now,
      ),
    ).toBe('COMPLETED')
  })
})

describe('nextResendAt', () => {
  it('allows resending one hour after the last email', () => {
    expect(
      nextResendAt({ last_sent_at: '2026-10-16T10:59:00Z' }, now),
    ).toBeNull()
    expect(nextResendAt({ last_sent_at: '2026-10-16T11:30:00Z' }, now)).toEqual(
      new Date('2026-10-16T12:30:00Z'),
    )
    expect(nextResendAt({ last_sent_at: null }, now)).toBeNull()
  })
})
