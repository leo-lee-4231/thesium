<script setup lang="ts">
import { CandlestickChart } from 'echarts/charts'
import { DataZoomComponent, GridComponent, TooltipComponent } from 'echarts/components'
import * as echarts from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'

import type { Candle } from '@/api/client'

echarts.use([CandlestickChart, GridComponent, TooltipComponent, DataZoomComponent, CanvasRenderer])

const props = defineProps<{
  candles: Candle[]
  timeframe: string
}>()

const chartEl = ref<HTMLDivElement | null>(null)
let chart: echarts.ECharts | null = null
let observer: ResizeObserver | null = null

function formatTime(value: string): string {
  const date = new Date(value)
  if (props.timeframe === '1d') {
    return date.toLocaleDateString('zh-CN', {
      month: '2-digit',
      day: '2-digit',
      timeZone: 'Asia/Shanghai',
    })
  }
  return date.toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    timeZone: 'Asia/Shanghai',
  })
}

function render(): void {
  if (!chartEl.value) return
  if (!chart) chart = echarts.init(chartEl.value)

  const categories = props.candles.map((candle) => formatTime(candle.open_time))
  const values = props.candles.map((candle) => [
    Number(candle.open),
    Number(candle.close),
    Number(candle.low),
    Number(candle.high),
  ])

  chart.setOption(
    {
      backgroundColor: 'transparent',
      animation: false,
      grid: { left: 8, right: 8, top: 12, bottom: 42, containLabel: true },
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'cross' },
        backgroundColor: 'rgba(10, 14, 19, 0.94)',
        borderColor: 'rgba(148, 163, 184, 0.25)',
        textStyle: { color: '#e8eef6', fontSize: 11 },
      },
      xAxis: {
        type: 'category',
        data: categories,
        boundaryGap: true,
        axisLine: { lineStyle: { color: 'rgba(148, 163, 184, 0.2)' } },
        axisLabel: { color: '#93a4b8', fontSize: 10 },
      },
      yAxis: {
        scale: true,
        position: 'right',
        splitLine: { lineStyle: { color: 'rgba(148, 163, 184, 0.08)' } },
        axisLabel: { color: '#93a4b8', fontSize: 10 },
      },
      dataZoom: [
        { type: 'inside', start: 55, end: 100 },
        {
          type: 'slider',
          height: 14,
          bottom: 0,
          borderColor: 'transparent',
          backgroundColor: 'rgba(148, 163, 184, 0.08)',
          fillerColor: 'rgba(110, 231, 183, 0.15)',
          handleStyle: { color: '#6ee7b7' },
          textStyle: { color: '#93a4b8', fontSize: 9 },
        },
      ],
      series: [
        {
          type: 'candlestick',
          data: values,
          itemStyle: {
            color: '#6ee7b7',
            color0: '#f87171',
            borderColor: '#6ee7b7',
            borderColor0: '#f87171',
          },
        },
      ],
    },
    true,
  )
}

onMounted(() => {
  render()
  observer = new ResizeObserver(() => chart?.resize())
  if (chartEl.value) observer.observe(chartEl.value)
})

watch(
  () => props.candles,
  () => render(),
  { deep: true },
)

watch(
  () => props.timeframe,
  () => render(),
)

onBeforeUnmount(() => {
  observer?.disconnect()
  chart?.dispose()
})
</script>

<template>
  <div ref="chartEl" class="price-chart"></div>
</template>