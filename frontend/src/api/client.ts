import axios from 'axios'

import { tokenStorage } from '@/lib/storage'

/** Shared axios instance for all Django API calls. */
export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_URL ?? '/api',
})

// Attach credentials to every request.
// X-Device-Token lets the backend skip 2FA on a trusted device and mark
// the current device in /devices/ (see accounts.utils.extract_raw_device_token).
apiClient.interceptors.request.use((config) => {
  const access = tokenStorage.getAccess()
  const deviceToken = tokenStorage.getDeviceToken()

  if (access) config.headers.set('Authorization', `Bearer ${access}`)
  if (deviceToken) config.headers.set('X-Device-Token', deviceToken)

  return config
})
