import { useEffect, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'

interface Props {
  value: string // 'YYYY-MM'
  onChange: (v: string) => void
  min?: string // 'YYYY-MM' inclusive
  max?: string // 'YYYY-MM' inclusive
  placeholder?: string
}

const MONTHS = ['1月', '2月', '3月', '4月', '5月', '6月', '7月', '8月', '9月', '10月', '11月', '12月']

const pad = (n: number) => String(n).padStart(2, '0')
const toKey = (y: number, m: number) => `${y}-${pad(m)}`

function parse(v: string): { y: number; m: number } {
  const [y, m] = (v || '').split('-').map(Number)
  if (!y || !m) {
    const now = new Date()
    return { y: now.getFullYear(), m: now.getMonth() + 1 }
  }
  return { y, m }
}

export function MonthPicker({ value, onChange, min, max, placeholder }: Props) {
  const [open, setOpen] = useState(false)
  const cur = parse(value)
  const [viewYear, setViewYear] = useState(cur.y)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (open) setViewYear(parse(value).y)
  }, [open, value])

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const isDisabled = (y: number, m: number) => {
    const k = toKey(y, m)
    if (min && k < min) return true
    if (max && k > max) return true
    return false
  }

  const select = (m: number) => {
    if (isDisabled(viewYear, m)) return
    onChange(toKey(viewYear, m))
    setOpen(false)
  }

  const minYear = min ? Number(min.slice(0, 4)) : viewYear - 30
  const maxYear = max ? Number(max.slice(0, 4)) : viewYear + 5
  const hasValue = Boolean(value)

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className={`flex w-full items-center justify-between rounded-xl border bg-slate-900/60 px-3 py-2 text-sm transition focus:outline-none ${
          open ? 'border-sky-400/70 ring-2 ring-sky-500/20' : 'border-slate-700/60 hover:border-sky-400/50'
        }`}
      >
        <span className={hasValue ? 'tabular-nums text-slate-100' : 'text-slate-500'}>
          {hasValue ? `${cur.y} 年 ${pad(cur.m)} 月` : placeholder || '选择月份'}
        </span>
        <svg className="h-4 w-4 text-slate-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <rect x="3" y="4" width="18" height="17" rx="2" />
          <path d="M3 9h18M8 2v4M16 2v4" />
        </svg>
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: -6, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -6, scale: 0.97 }}
            transition={{ duration: 0.14 }}
            className="absolute z-30 mt-2 w-[260px] max-w-[calc(100vw-2rem)] rounded-2xl border border-slate-700/60 bg-slate-900/95 p-3 shadow-2xl shadow-black/40 backdrop-blur"
          >
            <div className="mb-2 flex items-center justify-between">
              <button
                type="button"
                disabled={viewYear <= minYear}
                onClick={() => setViewYear((y) => Math.max(minYear, y - 1))}
                className="flex h-8 w-8 items-center justify-center rounded-lg text-slate-300 transition hover:bg-slate-700/50 disabled:opacity-30"
              >
                ‹
              </button>
              <span className="text-sm font-semibold tabular-nums text-white">{viewYear} 年</span>
              <button
                type="button"
                disabled={viewYear >= maxYear}
                onClick={() => setViewYear((y) => Math.min(maxYear, y + 1))}
                className="flex h-8 w-8 items-center justify-center rounded-lg text-slate-300 transition hover:bg-slate-700/50 disabled:opacity-30"
              >
                ›
              </button>
            </div>
            <div className="grid grid-cols-3 gap-1.5">
              {MONTHS.map((label, i) => {
                const m = i + 1
                const selected = viewYear === cur.y && m === cur.m && hasValue
                const disabled = isDisabled(viewYear, m)
                return (
                  <button
                    key={m}
                    type="button"
                    disabled={disabled}
                    onClick={() => select(m)}
                    className={`rounded-lg py-2 text-sm transition ${
                      selected
                        ? 'bg-gradient-to-r from-sky-500 to-violet-500 font-medium text-white shadow'
                        : disabled
                          ? 'cursor-not-allowed text-slate-600 opacity-40'
                          : 'text-slate-300 hover:bg-slate-700/50 hover:text-white'
                    }`}
                  >
                    {label}
                  </button>
                )
              })}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
