import { useCallback, useEffect, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import dayjs from 'dayjs'
import type { BacktestParams, BacktestResult, MarketInfo } from './types'
import { clearCache, fetchMarkets, runBacktest } from './api'
import { BacktestForm, type FormState } from './components/BacktestForm'
import { ResultCards } from './components/ResultCards'
import { GrowthChart } from './components/GrowthChart'
import { TransactionsTable } from './components/TransactionsTable'

const FALLBACK_MARKETS: MarketInfo[] = [
  { key: 'a', name: 'A股', currency: 'CNY', default_lot: 100, lot_is_uncertain: false, dividend_reliable: true },
  { key: 'hk', name: '港股', currency: 'HKD', default_lot: 100, lot_is_uncertain: true, dividend_reliable: false },
  { key: 'us', name: '美股', currency: 'USD', default_lot: 1, lot_is_uncertain: false, dividend_reliable: false },
  { key: 'etf', name: '场内ETF', currency: 'CNY', default_lot: 100, lot_is_uncertain: false, dividend_reliable: false },
]

const DEFAULT_FORM: FormState = {
  market: 'a',
  code: '',
  name: '',
  start: '2005-01',
  end: dayjs().format('YYYY-MM'),
  strategy_type: 'amount',
  strategy_value: '3000',
  dividend_mode: 'reinvest',
  invest_day: '1',
  lot_override: '',
  lot: 100,
}

export default function App() {
  const [markets, setMarkets] = useState<MarketInfo[]>(FALLBACK_MARKETS)
  const [form, setForm] = useState<FormState>(DEFAULT_FORM)
  const [result, setResult] = useState<BacktestResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [clearing, setClearing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const ranOnceRef = useRef(false)

  useEffect(() => {
    fetchMarkets().then(setMarkets).catch(() => setMarkets(FALLBACK_MARKETS))
  }, [])

  const onChange = useCallback((patch: Partial<FormState>) => {
    setForm((f) => {
      const next = { ...f, ...patch }
      if (patch.market) {
        const cfg = (markets.find((m) => m.key === patch.market) ?? FALLBACK_MARKETS[0])
        next.lot = cfg.default_lot
      }
      return next
    })
  }, [markets])

  const run = useCallback(async () => {
    if (!form.code.trim()) {
      setError('请先输入股票/ETF 代码')
      return
    }
    const value = Number(form.strategy_value)
    if (!value || value <= 0) {
      setError('请输入有效的定投数值')
      return
    }
    setLoading(true)
    setError(null)
    const params: BacktestParams = {
      market: form.market,
      code: form.code.trim(),
      start: form.start,
      end: form.end,
      strategy_type: form.strategy_type,
      strategy_value: value,
      dividend_mode: form.dividend_mode,
      invest_day: Number(form.invest_day) || 1,
      lot_override: form.lot_override ? Number(form.lot_override) : null,
    }
    try {
      const r = await runBacktest(params)
      setResult(r)
      ranOnceRef.current = true
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setLoading(false)
    }
  }, [form])

  const clearCacheAndRerun = useCallback(async () => {
    if (!result || clearing) return
    setClearing(true)
    setError(null)
    try {
      await clearCache(result.summary.market, result.summary.code)
    } catch (e) {
      setError((e as Error).message)
      setClearing(false)
      return
    }
    setClearing(false)
    run()
  }, [result, clearing, run])

  // Re-run automatically when toggling 复投/不复投 after the first run.
  useEffect(() => {
    if (ranOnceRef.current) run()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [form.dividend_mode])

  return (
    <div className="min-h-full">
      <header className="mx-auto max-w-7xl px-5 pt-10 pb-6">
        <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }}>
          <h1 className="bg-gradient-to-r from-sky-300 via-white to-violet-300 bg-clip-text text-3xl font-bold tracking-tight text-transparent sm:text-4xl">
            DCA Lab
          </h1>
          <p className="mt-2 text-sm text-slate-400">
            A股 · 港股 · 美股 · ETF 月度定投模拟，支持按金额/按股数、分红再投入或不复投，数据本地缓存。
          </p>
        </motion.div>
      </header>

      <main className="mx-auto grid max-w-7xl grid-cols-1 gap-6 px-5 pb-16 lg:grid-cols-12">
        <div className="lg:col-span-4 xl:col-span-3">
          <div className="lg:sticky lg:top-6">
            <BacktestForm markets={markets} form={form} onChange={onChange} onRun={run} loading={loading} />
          </div>
        </div>

        <div className="lg:col-span-8 xl:col-span-9">
          <AnimatePresence>
            {error && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
                className="mb-4 rounded-xl border border-rose-500/40 bg-rose-500/10 px-4 py-3 text-sm text-rose-200"
              >
                {error}
              </motion.div>
            )}
          </AnimatePresence>

          {result && result.warnings.length > 0 && (
            <div className="mb-4 space-y-1 rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-xs text-amber-200">
              {result.warnings.map((w, i) => (
                <div key={i}>· {w}</div>
              ))}
            </div>
          )}

          {!result && !loading && (
            <div className="glass flex min-h-[460px] flex-col items-center justify-center rounded-2xl p-10 text-center">
              <div className="text-5xl">📈</div>
              <h2 className="mt-4 text-lg font-medium text-slate-200">输入标的，开始你的定投回测</h2>
              <p className="mt-2 max-w-md text-sm text-slate-400">
                选择市场并搜索股票/ETF，设定起止月份与每月投入，即可计算原始本金、当前价值、分红与年化收益。
              </p>
            </div>
          )}

          {loading && !result && (
            <div className="glass flex min-h-[460px] items-center justify-center rounded-2xl">
              <div className="flex items-center gap-3 text-slate-300">
                <span className="h-5 w-5 animate-spin rounded-full border-2 border-slate-500 border-t-sky-400" />
                正在获取数据并计算…
              </div>
            </div>
          )}

          {result && (
            <motion.div
              key={`${result.summary.code}-${result.summary.dividend_mode}`}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="space-y-6"
            >
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <h2 className="text-xl font-semibold text-white">
                  {result.summary.name}
                  <span className="ml-2 text-sm font-normal text-slate-400">
                    {result.summary.code} · {result.summary.start} ~ {result.summary.end}
                  </span>
                </h2>
                <div className="flex items-center gap-2">
                  <span className="rounded-full border border-slate-600/50 px-3 py-1 text-xs text-slate-300">
                    {result.summary.dividend_mode === 'reinvest' ? '分红再投入' : '分红不复投'}
                  </span>
                  <button
                    type="button"
                    onClick={clearCacheAndRerun}
                    disabled={clearing || loading}
                    title="删除该标的的本地缓存并重新拉取最新数据"
                    className="rounded-full border border-slate-600/50 px-3 py-1 text-xs text-slate-300 transition hover:border-rose-400/60 hover:text-rose-300 disabled:opacity-40"
                  >
                    {clearing ? '清除中…' : '🗑 清除缓存并重算'}
                  </button>
                </div>
              </div>
              <ResultCards summary={result.summary} />
              <GrowthChart timeline={result.timeline} currency={result.summary.currency} />
              <TransactionsTable transactions={result.transactions} summary={result.summary} />
            </motion.div>
          )}
        </div>
      </main>

      <footer className="mx-auto max-w-7xl px-5 pb-10 text-center text-xs text-slate-600">
        数据来源：akshare（行情/分红），仅供研究参考，不构成投资建议。
      </footer>
    </div>
  )
}
