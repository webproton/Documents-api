import { useEffect } from 'react'
import { Outlet, useMatches } from 'react-router'

/** Route `handle` used for the browser tab title. */
export interface RouteHandle {
  title?: string
}

const APP_NAME = 'Documents'

/** Root of every route: keeps document.title in sync with the page. */
export function RootLayout() {
  const matches = useMatches()
  // The deepest route that declares a title wins
  const title = [...matches]
    .reverse()
    .map((match) => (match.handle as RouteHandle | undefined)?.title)
    .find(Boolean)

  useEffect(() => {
    document.title = title ? `${title} · ${APP_NAME}` : APP_NAME
  }, [title])

  return <Outlet />
}
