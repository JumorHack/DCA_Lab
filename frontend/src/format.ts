const CURRENCY_SYMBOL: Record<string, string> = {
  CNY: '¥',
  HKD: 'HK$',
  USD: '$',
}

export function currencySymbol(cur?: string): string {
  return (cur && CURRENCY_SYMBOL[cur]) || ''
}

export function money(value: number | null | undefined, currency = 'CNY'): string {
  if (value == null || Number.isNaN(value)) return '--'
  return (
    currencySymbol(currency) +
    value.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
  )
}

export function compactMoney(value: number | null | undefined, currency = 'CNY'): string {
  if (value == null || Number.isNaN(value)) return '--'
  return currencySymbol(currency) + value.toLocaleString('en-US', { maximumFractionDigits: 0 })
}

export function percent(value: number | null | undefined, digits = 2): string {
  if (value == null || Number.isNaN(value)) return '--'
  const v = value * 100
  return `${v >= 0 ? '+' : ''}${v.toFixed(digits)}%`
}

export function number(value: number | null | undefined, digits = 2): string {
  if (value == null || Number.isNaN(value)) return '--'
  return value.toLocaleString('en-US', { maximumFractionDigits: digits })
}
