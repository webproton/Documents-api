import type { ReactNode } from 'react'

interface CardProps {
  title: string
  description?: string
  children: ReactNode
}

/** White section with a heading, used on settings-like pages. */
export function Card({ title, description, children }: CardProps) {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-6">
      <h2 className="text-lg font-semibold">{title}</h2>
      {description && (
        <p className="mt-1 text-sm text-slate-500">{description}</p>
      )}
      <div className="mt-4">{children}</div>
    </section>
  )
}
