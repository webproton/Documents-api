import { isRouteErrorResponse, Link, useRouteError } from 'react-router'

import { paths } from '@/routes/paths'

/** Shown instead of a blank screen when a page crashes while rendering. */
export function ErrorPage() {
  const error = useRouteError()
  const details = isRouteErrorResponse(error)
    ? `${error.status} ${error.statusText}`
    : error instanceof Error
      ? error.message
      : null

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-slate-50 px-4 text-center text-slate-900">
      <h1 className="text-xl font-semibold">Something went wrong</h1>
      <p className="max-w-md text-sm text-slate-500">
        The page could not be displayed. Try reloading it; if the problem
        persists, contact support.
      </p>
      {import.meta.env.DEV && details && (
        <pre className="max-w-xl overflow-x-auto rounded-md bg-slate-100 px-3 py-2 text-left text-xs text-slate-600">
          {details}
        </pre>
      )}
      <div className="flex gap-4 text-sm font-medium">
        <button
          type="button"
          onClick={() => window.location.reload()}
          className="text-blue-600 hover:underline"
        >
          Reload
        </button>
        <Link to={paths.home} className="text-blue-600 hover:underline">
          Go to home page
        </Link>
      </div>
    </div>
  )
}
