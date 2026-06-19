import { useEffect, useRef, useState } from 'react'

function useCountUp(target: number, duration = 900): number {
  const [val, setVal] = useState(0)
  const valRef = useRef(0)
  valRef.current = val
  const rafRef = useRef(0)

  useEffect(() => {
    const from = valRef.current
    const safeTarget = Number.isFinite(target) ? target : 0
    const start = performance.now()
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / duration)
      const eased = 1 - Math.pow(1 - t, 3)
      setVal(from + (safeTarget - from) * eased)
      if (t < 1) rafRef.current = requestAnimationFrame(tick)
    }
    cancelAnimationFrame(rafRef.current)
    rafRef.current = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(rafRef.current)
  }, [target, duration])

  return val
}

export function AnimatedNumber({
  value,
  format,
  duration,
}: {
  value: number
  format: (n: number) => string
  duration?: number
}) {
  const animated = useCountUp(value, duration)
  return <>{format(animated)}</>
}
