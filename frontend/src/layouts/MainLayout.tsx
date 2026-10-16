import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, NavLink, Outlet } from 'react-router'

import { profileApi } from '@/api/profile'
import { Button } from '@/components/ui/Button'
import { useAuth } from '@/features/auth/auth-context'
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

/** Shell for authenticated pages: header with navigation + page content. */
export function MainLayout() {
  const { signOut } = useAuth()
  const [signingOut, setSigningOut] = useState(false)
  const profile = useQuery({ queryKey: ['profile'], queryFn: profileApi.get })

  const handleSignOut = async () => {
    setSigningOut(true)
    // ProtectedRoute redirects to login once the session is gone
    await signOut()
  }

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3">
          <Link to={paths.home} className="text-lg font-semibold">
            Documents
          </Link>
          <nav className="flex flex-wrap gap-1 text-sm">
            {navItems.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  `rounded-md px-3 py-1.5 ${
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
          <div className="ml-auto flex items-center gap-3 text-sm">
            {profile.data && (
              <span className="text-slate-600">{profile.data.email}</span>
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
      <main className="mx-auto max-w-6xl px-4 py-8">
        <Outlet />
      </main>
    </div>
  )
}
