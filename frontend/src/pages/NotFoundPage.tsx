import { Link } from 'react-router'

import { paths } from '@/routes/paths'

export function NotFoundPage() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-slate-50 px-4 text-center text-slate-900">
      <p className="text-6xl font-bold text-slate-300">404</p>
      <h1 className="text-xl font-semibold">Page not found</h1>
      <Link to={paths.home} className="text-sm text-blue-600 hover:underline">
        Go to home page
      </Link>
    </div>
  )
}
