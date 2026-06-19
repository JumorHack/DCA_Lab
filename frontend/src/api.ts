import axios from 'axios'
import type { BacktestParams, BacktestResult, Instrument, MarketInfo } from './types'

const client = axios.create({ baseURL: '/api', timeout: 90000 })

function extractError(err: unknown): string {
  if (axios.isAxiosError(err)) {
    const detail = err.response?.data?.detail
    if (typeof detail === 'string') return detail
    if (err.code === 'ECONNABORTED') return '请求超时，数据源响应较慢，请重试'
    return err.message || '请求失败'
  }
  return (err as Error)?.message || '未知错误'
}

export async function fetchMarkets(): Promise<MarketInfo[]> {
  const { data } = await client.get('/markets')
  return data.markets
}

export async function searchInstruments(market: string, q: string): Promise<Instrument[]> {
  const { data } = await client.get('/search', { params: { market, q } })
  return data.results
}

export async function clearCache(
  market: string,
  code: string,
): Promise<{ ok: boolean; code: string; deleted: Record<string, number> }> {
  const { data } = await client.delete('/cache', { params: { market, code } })
  return data
}

export async function runBacktest(params: BacktestParams): Promise<BacktestResult> {
  try {
    const { data } = await client.post('/backtest', params)
    return data
  } catch (err) {
    throw new Error(extractError(err))
  }
}

export { extractError }
