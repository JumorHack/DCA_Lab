export type MarketKey = 'a' | 'hk' | 'us' | 'etf'
export type StrategyType = 'amount' | 'shares'
export type DividendMode = 'reinvest' | 'cash'

export interface MarketInfo {
  key: MarketKey
  name: string
  currency: string
  default_lot: number
  lot_is_uncertain: boolean
  dividend_reliable: boolean
}

export interface Instrument {
  market: string
  code: string
  name: string
  lot: number
  currency: string
  ak_symbol?: string
}

export interface BacktestParams {
  market: MarketKey
  code: string
  start: string
  end: string
  strategy_type: StrategyType
  strategy_value: number
  dividend_mode: DividendMode
  invest_day?: number
  lot_override?: number | null
}

export interface Summary {
  market: string
  code: string
  name: string
  currency: string
  lot: number
  dividend_mode: DividendMode
  strategy_type: StrategyType
  strategy_value: number
  start: string
  end: string
  end_date: string
  months: number
  principal: number
  current_value: number
  dividend_total: number
  leftover_cash: number
  shares_held: number
  end_price: number
  total_return_pct: number | null
  annualized: number | null
  dividend_estimated: boolean
}

export interface TimelinePoint {
  date: string
  invested: number
  value: number
  dividend: number
}

export interface Transaction {
  date: string
  price: number
  shares: number
  cost: number
  leftover: number
}

export interface BacktestResult {
  summary: Summary
  timeline: TimelinePoint[]
  transactions: Transaction[]
  warnings: string[]
}
