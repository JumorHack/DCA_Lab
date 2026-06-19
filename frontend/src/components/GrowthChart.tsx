import { useEffect, useMemo, useRef, useState } from 'react'
import ReactECharts from 'echarts-for-react'
import { motion } from 'framer-motion'
import type { TimelinePoint } from '../types'
import { compactMoney, money } from '../format'

export function GrowthChart({
  timeline,
  currency,
}: {
  timeline: TimelinePoint[]
  currency: string
}) {
  const [visible, setVisible] = useState(timeline.length)
  const [playing, setPlaying] = useState(false)
  const timerRef = useRef<number | undefined>(undefined)

  useEffect(() => {
    setVisible(timeline.length)
    setPlaying(false)
    if (timerRef.current) window.clearInterval(timerRef.current)
  }, [timeline])

  useEffect(() => () => { if (timerRef.current) window.clearInterval(timerRef.current) }, [])

  const play = () => {
    if (timerRef.current) window.clearInterval(timerRef.current)
    if (timeline.length <= 1) return
    setPlaying(true)
    let i = 1
    setVisible(1)
    const step = Math.max(45, Math.round(1500 / timeline.length))
    timerRef.current = window.setInterval(() => {
      i += 1
      setVisible(i)
      if (i >= timeline.length) {
        if (timerRef.current) window.clearInterval(timerRef.current)
        setPlaying(false)
      }
    }, step)
  }

  const data = useMemo(() => timeline.slice(0, Math.max(visible, 1)), [timeline, visible])

  const option = useMemo(() => {
    const dates = data.map((d) => d.date)
    return {
      backgroundColor: 'transparent',
      grid: { left: 8, right: 16, top: 48, bottom: 28, containLabel: true },
      legend: {
        top: 8,
        textStyle: { color: '#cbd5e1' },
        data: ['累计投入', '市值', '累计分红'],
      },
      tooltip: {
        trigger: 'axis',
        backgroundColor: 'rgba(15,23,42,0.92)',
        borderColor: 'rgba(148,163,184,0.25)',
        textStyle: { color: '#e2e8f0' },
        valueFormatter: (v: number) => money(v, currency),
      },
      xAxis: {
        type: 'category',
        boundaryGap: false,
        data: dates,
        axisLine: { lineStyle: { color: 'rgba(148,163,184,0.25)' } },
        axisLabel: { color: '#94a3b8', hideOverlap: true },
      },
      yAxis: {
        type: 'value',
        scale: true,
        splitLine: { lineStyle: { color: 'rgba(148,163,184,0.12)' } },
        axisLabel: { color: '#94a3b8', formatter: (v: number) => compactMoney(v, currency) },
      },
      series: [
        {
          name: '累计投入',
          type: 'line',
          smooth: true,
          showSymbol: false,
          lineStyle: { width: 2, color: '#38bdf8' },
          areaStyle: {
            color: {
              type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
              colorStops: [
                { offset: 0, color: 'rgba(56,189,248,0.28)' },
                { offset: 1, color: 'rgba(56,189,248,0.02)' },
              ],
            },
          },
          data: data.map((d) => d.invested),
        },
        {
          name: '市值',
          type: 'line',
          smooth: true,
          showSymbol: false,
          lineStyle: { width: 2.5, color: '#34d399' },
          areaStyle: {
            color: {
              type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
              colorStops: [
                { offset: 0, color: 'rgba(52,211,153,0.32)' },
                { offset: 1, color: 'rgba(52,211,153,0.02)' },
              ],
            },
          },
          data: data.map((d) => d.value),
        },
        {
          name: '累计分红',
          type: 'line',
          smooth: true,
          showSymbol: false,
          lineStyle: { width: 1.5, color: '#fbbf24', type: 'dashed' },
          data: data.map((d) => d.dividend),
        },
      ],
      animationDuration: 600,
      animationEasing: 'cubicOut' as const,
    }
  }, [data, currency])

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.1 }}
      className="glass rounded-2xl p-4"
    >
      <div className="mb-1 flex items-center justify-between px-1">
        <h3 className="text-sm font-medium text-slate-200">本金 vs 市值 走势</h3>
        <button
          onClick={play}
          disabled={playing}
          className="rounded-lg border border-slate-600/50 bg-slate-800/60 px-3 py-1 text-xs text-slate-200 transition hover:border-sky-400/60 hover:text-sky-300 disabled:opacity-50"
        >
          {playing ? '播放中…' : '▶ 按月播放'}
        </button>
      </div>
      <ReactECharts option={option} style={{ height: 380 }} notMerge={false} lazyUpdate />
    </motion.div>
  )
}
