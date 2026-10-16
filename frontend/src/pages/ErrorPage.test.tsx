import { render, screen } from '@testing-library/react'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { describe, expect, it, vi } from 'vitest'

import { RootLayout } from '@/routes/RootLayout'

import { ErrorPage } from './ErrorPage'

function Broken(): never {
  throw new Error('Cannot read properties of undefined')
}

describe('ErrorPage', () => {
  it('replaces a crashed page instead of showing a blank screen', async () => {
    // React logs the caught error; keep the test output clean
    vi.spyOn(console, 'error').mockImplementation(() => {})
    const router = createMemoryRouter([
      {
        element: <RootLayout />,
        errorElement: <ErrorPage />,
        children: [{ path: '/', element: <Broken /> }],
      },
    ])

    render(<RouterProvider router={router} />)

    expect(
      await screen.findByRole('heading', { name: 'Something went wrong' }),
    ).toBeInTheDocument()
    // Details only in development builds
    expect(
      screen.getByText('Cannot read properties of undefined'),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('link', { name: 'Go to home page' }),
    ).toBeInTheDocument()
  })
})
