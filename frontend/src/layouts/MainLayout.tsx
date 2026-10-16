import { useState } from 'react'
import { Link, NavLink, Outlet } from 'react-router'

import { Button } from '@/components/ui/Button'
import { useAuth } from '@/features/auth/auth-context'
import { useProfile } from '@/features/profile/useProfile'
import { paths } from '@/routes/paths'

const navItems = [
  { to: paths.documents, label: 'Documents' },
  { to: paths.documentTypes, label: 'Types' },
  { to: paths.requests, label: 'Requests' },
  { to: paths.notifications, label: 'Notifications' },
  { to: paths.billing, label: 'Billing' },
  { to: paths.profile, label: 'Profile' },
  { to: paths.security, label: 'Security' },
]

/**
 * Shell for authenticated pages: header with navigation + page content.
 * One <nav> for all widths: a row on large screens, a collapsible
 * menu behind the ☰ button on phones.
 */
export function MainLayout() {
  const { signOut } = useAuth()
  const [signingOut, setSigningOut] = useState(false)
  const [menuOpen, setMenuOpen] = useState(false)
  const profile = useProfile()

  const handleSignOut = async () => {
    setSigningOut(true)
    // ProtectedRoute redirects to login once the session is gone
    await signOut()
  }

  // Hidden on small screens unless the menu is open; always shown on lg+
  const collapsible = `${menuOpen ? 'flex' : 'hidden'} w-full lg:flex lg:w-auto`

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-6 gap-y-3 px-4 py-3">
          <Link to={paths.home} className="text-lg font-semibold">
            Documents
          </Link>

          <button
            type="button"
            aria-label="Menu"
            aria-expanded={menuOpen}
            aria-controls="main-navigation"
            onClick={() => setMenuOpen((open) => !open)}
            className="ml-auto rounded-md border border-slate-300 px-3 py-1.5 text-lg leading-none lg:hidden"
          >
            {menuOpen ? '×' : '☰'}
          </button>

          <nav
            id="main-navigation"
            aria-label="Main"
            className={`${collapsible} flex-col gap-1 text-sm lg:flex-row lg:flex-wrap`}
          >
            {navItems.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                onClick={() => setMenuOpen(false)}
                className={({ isActive }) =>
                  `rounded-md px-3 py-2 lg:py-1.5 ${
                    isActive
                      ? 'bg-slate-900 text-white'
                      : 'text-slate-600 hover:bg-slate-100'
                  }`
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>

          <div
            className={`${collapsible} flex-wrap items-center gap-3 border-t border-slate-200 pt-3 text-sm lg:ml-auto lg:border-0 lg:pt-0`}
          >
            {profile.data && (
              <span className="truncate text-slate-600">
                {profile.data.email}
              </span>
            )}
            <Button
              variant="secondary"
              loading={signingOut}
              onClick={handleSignOut}
            >
              Log out
            </Button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-6 sm:py-8">
        <Outlet />
      </main>
    </div>
  )
}
