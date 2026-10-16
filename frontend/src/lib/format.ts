const dateTimeFormat = new Intl.DateTimeFormat('en-GB', {
  dateStyle: 'medium',
  timeStyle: 'short',
})

const dateFormat = new Intl.DateTimeFormat('en-GB', { dateStyle: 'medium' })

/** "16 Oct 2026, 12:44" in the user's time zone. */
export function formatDateTime(iso: string): string {
  return dateTimeFormat.format(new Date(iso))
}

/** "14 Jan 2027" */
export function formatDate(iso: string): string {
  return dateFormat.format(new Date(iso))
}
