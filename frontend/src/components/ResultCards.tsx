import { motion } from 'framer-motion'
import type { Summary } from '../types'
import { AnimatedNumber } from './AnimatedNumber'
import { money } from '../format'

interface CardDef {
  key: string
  label: string
  value: number
  render: (n: number) => string
  accent: string
  sub?: string
}

const pctText = (v: number | null, n: number) =>
  v == null ? '--' : `${n >= 0 ? '+' : ''}${n.toFixed(2)}%`

export function ResultCards({ summary }: { summary: Summary }) {
  const cur = summary.currency
  const gain = summary.current_value - summary.principal
  const positive = gain >= 0
  const annUp = (summary.annualized ?? 0) >= 0

  const cards: CardDef[] = [
    {
      key: 'principal',
      label: '原始本金',
      value: summary.principal,
      render: (n) => money(n, cur),
      accent: 'from-sky-400/20 to-sky-500/5',
      sub: `${summary.months} 期 · 每月${summary.strategy_type === 'amount' ? money(summary.strategy_value, cur) : `${summary.strategy_value} 股`}`,
    },
    {
      key: 'value',
      label: '当前价值',
      value: summary.current_value,
      render: (n) => money(n, cur),
      accent: positive ? 'from-emerald-400/25 to-emerald-500/5' : 'from-rose-400/25 to-rose-500/5',
      sub: `${positive ? '盈利' : '亏损'} ${money(Math.abs(gain), cur)}`,
    },
    {
      key: 'total_return',
      label: '总收益率',
      value: (summary.total_return_pct ?? 0) * 100,
      render: (n) => pctText(summary.total_return_pct, n),
      accent: positive ? 'from-emerald-400/25 to-emerald-500/5' : 'from-rose-400/25 to-rose-500/5',
      sub: '相对原始本金',
    },
    {
      key: 'dividend',
      label: summary.dividend_estimated ? '分红金额 (估算)' : '分红金额',
      value: summary.dividend_total,
      render: (n) => money(n, cur),
      accent: 'from-amber-300/25 to-amber-500/5',
      sub: summary.dividend_mode === 'reinvest' ? '已自动再投入' : '以现金计入',
    },
    {
      key: 'annual',
      label: '平均年化 (XIRR)',
      value: (summary.annualized ?? 0) * 100,
      render: (n) => pctText(summary.annualized, n),
      accent: annUp ? 'from-violet-400/25 to-violet-500/5' : 'from-rose-400/25 to-rose-500/5',
      sub: '资金加权内部收益率',
    },
  ]

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {cards.map((c, i) => (
        <motion.div
          key={c.key}
          initial={{ opacity: 0, y: 18, scale: 0.97 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          transition={{ delay: i * 0.07, type: 'spring', stiffness: 120, damping: 16 }}
          className="glass relative flex min-h-[140px] flex-col overflow-hidden rounded-2xl p-6"
        >
          <div className={`pointer-events-none absolute inset-0 bg-gradient-to-br ${c.accent}`} />
          <div className="relative flex flex-1 flex-col">
            <div className="text-sm text-slate-400">{c.label}</div>
            <div className="mt-3 whitespace-nowrap text-2xl font-semibold leading-tight tracking-tight text-white tabular-nums sm:text-[1.75rem]">
              <AnimatedNumber value={c.value} format={c.render} />
            </div>
            {c.sub && <div className="mt-auto pt-3 text-xs text-slate-400">{c.sub}</div>}
          </div>
        </motion.div>
      ))}
    </div>
  )
}
