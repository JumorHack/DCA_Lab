import { motion } from 'framer-motion'
import type { Summary, Transaction } from '../types'
import { money, number } from '../format'

export function TransactionsTable({
  transactions,
  summary,
}: {
  transactions: Transaction[]
  summary: Summary
}) {
  const cur = summary.currency
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.15 }}
      className="glass rounded-2xl p-4"
    >
      <h3 className="mb-3 px-1 text-sm font-medium text-slate-200">
        定投明细 <span className="text-slate-500">({transactions.length} 期)</span>
      </h3>
      <div className="max-h-[380px] overflow-auto rounded-xl border border-slate-700/40">
        <table className="w-full text-sm">
          <thead className="sticky top-0 bg-slate-900/90 text-xs uppercase text-slate-400 backdrop-blur">
            <tr>
              <th className="px-3 py-2 text-left font-medium">日期</th>
              <th className="px-3 py-2 text-right font-medium">价格</th>
              <th className="px-3 py-2 text-right font-medium">买入股数</th>
              <th className="px-3 py-2 text-right font-medium">投入金额</th>
              <th className="px-3 py-2 text-right font-medium">滚存现金</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60">
            {transactions.map((t, i) => (
              <tr key={`${t.date}-${i}`} className="text-slate-200 hover:bg-slate-800/40">
                <td className="px-3 py-2 text-left tabular-nums text-slate-300">{t.date}</td>
                <td className="px-3 py-2 text-right tabular-nums">{number(t.price, 3)}</td>
                <td className={`px-3 py-2 text-right tabular-nums ${t.shares > 0 ? '' : 'text-slate-500'}`}>
                  {number(t.shares, 2)}
                </td>
                <td className="px-3 py-2 text-right tabular-nums">{money(t.cost, cur)}</td>
                <td className="px-3 py-2 text-right tabular-nums text-slate-400">{money(t.leftover, cur)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </motion.div>
  )
}
