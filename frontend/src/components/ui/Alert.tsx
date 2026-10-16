import type { ReactNode } from 'react'

interface AlertProps {
  variant?: 'error' | 'success' | 'info'
  children: ReactNode
}

const variants = {
  error: 'border-red-200 bg-red-50 text-red-700',
  success: 'border-green-200 bg-green-50 text-green-700',
  info: 'border-slate-200 bg-slate-50 text-slate-700',
}

export function Alert({ variant = 'info', children }: AlertProps) {
  return (
    <div
      role={variant === 'error' ? 'alert' : 'status'}
      className={`rounded-md border px-3 py-2 text-sm ${variants[variant]}`}
    >
      {children}
    </div>
  )
}
