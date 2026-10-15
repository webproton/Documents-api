import { RouterProvider } from 'react-router'

import { AppProviders } from '@/AppProviders'
import { createAppRouter } from '@/routes/router'

const router = createAppRouter()

export default function App() {
  return (
    <AppProviders>
      <RouterProvider router={router} />
    </AppProviders>
  )
}
