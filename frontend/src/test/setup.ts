import '@testing-library/jest-dom/vitest'
import { cleanup, configure } from '@testing-library/react'
import { afterAll, afterEach, beforeAll } from 'vitest'

import { server } from './server'

// findBy*/waitFor default is 1 s — too tight for a loaded Docker/CI run.
// They still resolve as soon as the element appears.
configure({ asyncUtilTimeout: 3000 })

// Any request without a handler fails the test instead of hitting the network
beforeAll(() => server.listen({ onUnhandledFrame: 'error' }))

afterEach(() => {
  cleanup()
  server.resetHandlers()
  localStorage.clear()
})

afterAll(() => server.close())
