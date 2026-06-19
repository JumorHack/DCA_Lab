import { useEffect, useRef, useState } from 'react'
import type { DividendMode, Instrument, MarketInfo, MarketKey, StrategyType } from '../types'
import { searchInstruments } from '../api'
import { MonthPicker } from './MonthPicker'

const _now = new Date()
const NOW_MONTH = `${_now.getFullYear()}-${String(_now.getMonth() + 1).padStart(2, '0')}`
const monthsAgo = (n: number) => {
  const d = new Date()
  d.setMonth(d.getMonth() - n)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
}
const RANGE_PRESETS: { label: string; range: () => { start: string; end: string } }[] = [
  { label: '近1年', range: () => ({ start: monthsAgo(12), end: NOW_MONTH }) },
  { label: '近3年', range: () => ({ start: monthsAgo(36), end: NOW_MONTH }) },
  { label: '近5年', range: () => ({ start: monthsAgo(60), end: NOW_MONTH }) },
  { label: '今年以来', range: () => ({ start: `${_now.getFullYear()}-01`, end: NOW_MONTH }) },
]

export interface FormState {
  market: MarketKey
  code: string
  name: string
  start: string
  end: string
  strategy_type: StrategyType
  strategy_value: string
  dividend_mode: DividendMode
  invest_day: string
  lot_override: string
  lot: number
}

interface Props {
  markets: MarketInfo[]
  form: FormState
  onChange: (patch: Partial<FormState>) => void
  onRun: () => void
  loading: boolean
}

function Segmented<T extends string>({
  value,
  options,
  onChange,
}: {
  value: T
  options: { value: T; label: string }[]
  onChange: (v: T) => void
}) {
  return (
    <div className="flex rounded-xl bg-slate-800/50 p-1">
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          onClick={() => onChange(o.value)}
          className={`flex-1 rounded-lg px-3 py-2 text-sm font-medium transition ${
            value === o.value
              ? 'bg-gradient-to-r from-sky-500 to-violet-500 text-white shadow'
              : 'text-slate-300 hover:text-white'
          }`}
        >
          {o.label}
        </button>
      ))}
    </div>
  )
}

const fieldCls =
  'w-full rounded-xl border border-slate-700/60 bg-slate-900/60 px-3 py-2 text-sm text-slate-100 outline-none transition focus:border-sky-400/70 focus:ring-2 focus:ring-sky-500/20'
const labelCls = 'mb-1.5 block text-xs font-medium text-slate-400'

export function BacktestForm({ markets, form, onChange, onRun, loading }: Props) {
  const [query, setQuery] = useState(form.code)
  const [results, setResults] = useState<Instrument[]>([])
  const [open, setOpen] = useState(false)
  const [searching, setSearching] = useState(false)
  const boxRef = useRef<HTMLDivElement>(null)

  useEffect(() => setQuery(form.code), [form.market])

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  useEffect(() => {
    const q = query.trim()
    // 至少 2 个字符才搜索，并加长防抖，避免频繁触发全市场清单下载而被数据源限流。
    if (q.length < 2) {
      setResults([])
      setSearching(false)
      return
    }
    let active = true
    setSearching(true)
    const t = window.setTimeout(async () => {
      try {
        const r = await searchInstruments(form.market, q)
        if (active) {
          setResults(r)
          setOpen(true)
        }
      } catch {
        if (active) setResults([])
      } finally {
        if (active) setSearching(false)
      }
    }, 500)
    return () => {
      active = false
      window.clearTimeout(t)
    }
  }, [query, form.market])

  const pick = (inst: Instrument) => {
    onChange({ code: inst.code, name: inst.name, lot: inst.lot, lot_override: '' })
    setQuery(inst.code)
    setOpen(false)
  }

  const marketCfg = markets.find((m) => m.key === form.market)
  const currency = marketCfg?.currency ?? ''

  return (
    <div className="glass flex flex-col gap-4 rounded-2xl p-5">
      <div>
        <label className={labelCls}>市场</label>
        <Segmented
          value={form.market}
          onChange={(v) => onChange({ market: v, code: '', name: '' })}
          options={markets.map((m) => ({ value: m.key, label: m.name }))}
        />
      </div>

      <div ref={boxRef} className="relative">
        <label className={labelCls}>股票 / ETF 名称或代码</label>
        <input
          className={fieldCls}
          value={query}
          placeholder={form.market === 'us' ? '如 AAPL / 苹果' : '如 600519 / 贵州茅台'}
          onChange={(e) => {
            setQuery(e.target.value)
            onChange({ code: e.target.value, name: '' })
          }}
          onFocus={() => results.length && setOpen(true)}
        />
        {form.name && <div className="mt-1 text-xs text-sky-300/80">已选：{form.name}（{form.code}）</div>}
        {open && (results.length > 0 || searching) && (
          <div className="absolute z-20 mt-1 max-h-64 w-full overflow-auto rounded-xl border border-slate-700/60 bg-slate-900/95 shadow-xl backdrop-blur">
            {searching && <div className="px-3 py-2 text-xs text-slate-400">搜索中…</div>}
            {results.map((r) => (
              <button
                key={`${r.market}-${r.code}`}
                type="button"
                onClick={() => pick(r)}
                className="flex w-full items-center justify-between px-3 py-2 text-left text-sm text-slate-200 hover:bg-sky-500/15"
              >
                <span className="truncate">{r.name}</span>
                <span className="ml-2 shrink-0 text-xs text-slate-400">{r.code}</span>
              </button>
            ))}
          </div>
        )}
      </div>

      <div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className={labelCls}>开始月份</label>
            <MonthPicker
              value={form.start}
              max={form.end || NOW_MONTH}
              onChange={(v) => onChange({ start: v })}
            />
          </div>
          <div>
            <label className={labelCls}>结束月份</label>
            <MonthPicker
              value={form.end}
              min={form.start}
              max={NOW_MONTH}
              onChange={(v) => onChange({ end: v })}
            />
          </div>
        </div>
        <div className="mt-2 flex flex-wrap gap-1.5">
          {RANGE_PRESETS.map((p) => {
            const r = p.range()
            const active = form.start === r.start && form.end === r.end
            return (
              <button
                key={p.label}
                type="button"
                onClick={() => onChange(r)}
                className={`rounded-full border px-2.5 py-1 text-xs transition ${
                  active
                    ? 'border-sky-400/70 bg-sky-500/15 text-sky-300'
                    : 'border-slate-700/60 text-slate-400 hover:border-sky-400/60 hover:text-sky-300'
                }`}
              >
                {p.label}
              </button>
            )
          })}
        </div>
      </div>

      <div>
        <label className={labelCls}>定投策略</label>
        <Segmented
          value={form.strategy_type}
          onChange={(v) => onChange({ strategy_type: v })}
          options={[
            { value: 'amount', label: '按固定金额' },
            { value: 'shares', label: '按固定股数' },
          ]}
        />
        <div className="mt-3">
          <label className={labelCls}>
            {form.strategy_type === 'amount' ? `每月金额（${currency}）` : '每月股数'}
          </label>
          <input
            type="number"
            min={0}
            className={fieldCls}
            value={form.strategy_value}
            onChange={(e) => onChange({ strategy_value: e.target.value })}
            placeholder={form.strategy_type === 'amount' ? '如 3000' : '如 100'}
          />
          {form.strategy_type === 'amount' && (
            <p className="mt-1 text-xs text-slate-500">
              每月按 {form.lot_override || form.lot} 股/手买入最大整数手，不足金额滚存至下月。
            </p>
          )}
        </div>
      </div>

      <div>
        <label className={labelCls}>分红处理</label>
        <Segmented
          value={form.dividend_mode}
          onChange={(v) => onChange({ dividend_mode: v })}
          options={[
            { value: 'reinvest', label: '分红再投入' },
            { value: 'cash', label: '不复投' },
          ]}
        />
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className={labelCls}>每月定投日</label>
          <input
            type="number"
            min={1}
            max={28}
            className={fieldCls}
            value={form.invest_day}
            onChange={(e) => onChange({ invest_day: e.target.value })}
          />
        </div>
        <div>
          <label className={labelCls}>
            每手股数{marketCfg?.lot_is_uncertain ? ' *' : ''}
          </label>
          <input
            type="number"
            min={1}
            className={fieldCls}
            value={form.lot_override}
            onChange={(e) => onChange({ lot_override: e.target.value })}
            placeholder={`默认 ${form.lot}`}
          />
        </div>
      </div>
      {marketCfg?.lot_is_uncertain && (
        <p className="-mt-2 text-xs text-amber-400/80">* 港股每手股数因股而异，请按实际填写（默认 100）。</p>
      )}

      <button
        type="button"
        onClick={onRun}
        disabled={loading || !form.code.trim() || !form.strategy_value}
        className="mt-1 w-full rounded-xl bg-gradient-to-r from-sky-500 to-violet-500 px-4 py-3 text-sm font-semibold text-white shadow-lg shadow-sky-900/30 transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-40"
      >
        {loading ? '回测计算中…' : '开始回测'}
      </button>
    </div>
  )
}
