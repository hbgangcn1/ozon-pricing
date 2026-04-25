import { useEffect } from 'react'
import { useAuthStore } from '../stores/authStore'

const CHECK_INTERVAL_MS = 60 * 1000

export function useTokenRefresh() {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated)
  const shouldRefreshToken = useAuthStore((s) => s.shouldRefreshToken)
  const refreshToken = useAuthStore((s) => s.refreshToken)

  useEffect(() => {
    if (!isAuthenticated) return

    const checkAndRefresh = async () => {
      if (shouldRefreshToken()) {
        try {
          await refreshToken()
        } catch (_) {
          // Periodic refresh failed; will retry on next interval or next request
        }
      }
    }

    checkAndRefresh()

    const interval = setInterval(checkAndRefresh, CHECK_INTERVAL_MS)
    return () => clearInterval(interval)
  }, [isAuthenticated, shouldRefreshToken, refreshToken])
}