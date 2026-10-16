import { useCallback, useEffect, useState } from 'react'

/**
 * Seconds left until a deadline, ticking once per second.
 * Starts running immediately; restart() sets a new full period.
 */
export function useCountdown(seconds: number) {
  const [deadline, setDeadline] = useState(() => Date.now() + seconds * 1000)
  const [remaining, setRemaining] = useState(seconds)

  useEffect(() => {
    const tick = () =>
      setRemaining(Math.max(0, Math.ceil((deadline - Date.now()) / 1000)))
    tick()
    const timer = setInterval(tick, 1000)
    return () => clearInterval(timer)
  }, [deadline])

  const restart = useCallback(
    () => setDeadline(Date.now() + seconds * 1000),
    [seconds],
  )

  return { remaining, restart }
}
