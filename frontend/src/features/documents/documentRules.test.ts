import { describe, expect, it } from 'vitest'

import { daysUntil, expiryState, validateDocumentFile } from './documentRules'

const today = new Date(2026, 9, 16) // 16 Oct 2026, local time

describe('expiry', () => {
  it.each([
    ['2026-10-15', -1, 'expired'],
    ['2026-10-16', 0, 'expiring'],
    ['2026-11-15', 30, 'expiring'],
    ['2026-11-16', 31, 'valid'],
  ])('%s → %i days, %s', (date, days, state) => {
    expect(daysUntil(date, today)).toBe(days)
    expect(expiryState(date, today)).toBe(state)
  })
})

describe('validateDocumentFile', () => {
  const file = (name: string, size = 10) =>
    new File([new Uint8Array(size)], name)

  it.each(['a.pdf', 'b.XLSX', 'c.xls', 'd.csv'])('accepts %s', (name) => {
    expect(validateDocumentFile(file(name))).toBeNull()
  })

  it('rejects other formats', () => {
    expect(validateDocumentFile(file('a.docx'))).toMatch(/Unsupported/)
    expect(validateDocumentFile(file('noextension'))).toMatch(/Unsupported/)
  })

  it('rejects files over 10 MB', () => {
    expect(validateDocumentFile(file('a.pdf', 10 * 1024 * 1024 + 1))).toBe(
      'File must be at most 10MB',
    )
  })
})
