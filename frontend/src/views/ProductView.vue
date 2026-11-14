<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import { api, type Asset, type Candle, type MarketOverview, type Stream } from '@/api/client'
import PriceChart from '@/components/PriceChart.vue'

type Timeframe = '1h' | '4h' | '1d'

const route = useRoute()
const assets = ref<Asset[]>([])
const streams = ref<Stream[]>([])
const overview = ref<MarketOverview | null>(null)
const candles = ref<Candle[]>([])
const timeframe = ref<Timeframe>('1h')
const loading = ref(true)
const marketLoading = ref(false)
const error = ref<string | null>(null)

const symbol = computed(() => String(route.params.symbol ?? '').toUpperCase())
const asset = computed(() => assets.value.find((item) => item.symbol === symbol.value))
const stream = computed(() => streams.value.find((item) => item.asset_symbol === symbol.value))
const quote = computed(() => overview.value?.quote ?? null)
const derivative = computed(() => overview.value?.derivatives ?? null)
const indicatorEntries = computed(() =>
  Object.entries(overview.value?.indicators.timeframes ?? {}),
)
const change = computed(() => {
  const value = quote.value?.change_24h_pct
  return value === null || value === undefined ? null : Number(value)
})

const instrumentLabel = computed(() => {
  if (!asset.value || asset.value.instruments.length === 0) return '行情未配置'
  return asset.value.instruments
    .map(
      (instrument) =>
        `${instrument.provider.toUpperCase()} ${instrument.symbol} · ${instrument.market_type}`,
    )
    .join(' / ')
})

function fmt(value: string | null | undefined, digits = 2): string {
  if (value === null || value === undefined || value === '') return '—'
  const number = Number(value)
  if (!Number.isFinite(number)) return value
  return number.toLocaleString('en-US', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  })
}

function fmtPercent(value: string | null | undefined, digits = 2): string {
  if (value === null || value === undefined) return '—'
  const number = Number(value)
  if (!Number.isFinite(number)) return '—'
  return `${number > 0 ? '+' : ''}${number.toFixed(digits)}%`
}

function fmtFunding(value: string | null | undefined): string {
  if (value === null || value === undefined) return '—'
  const number = Number(value) * 100
  return `${number > 0 ? '+' : ''}${number.toFixed(4)}%`
}

function fmtTime(value: string | null | undefined): string {
  if (!value) return '—'
  return new Date(value).toLocaleString('zh-CN', {
    timeZone: 'Asia/Shanghai',
    hour12: false,
  })
}

async function load(): Promise<void> {
  loading.value = true
  const [assetsResult, streamsResult] = await Promise.allSettled([api.assets(), api.streams()])
  if (assetsResult.status === 'fulfilled') assets.value = assetsResult.value
  if (streamsResult.status === 'fulfilled') streams.value = streamsResult.value
  loading.value = false
  await loadMarket()
}

async function loadMarket(): Promise<void> {
  marketLoading.value = true
  error.value = null
  try {
    const [overviewResult, candlesResult] = await Promise.all([
      api.marketOverview(symbol.value),
      api.candles(symbol.value, timeframe.value, 220),
    ])
    overview.value = overviewResult
    candles.value = candlesResult.candles
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : 'OKX 行情暂时不可用'
  } finally {
    marketLoading.value = false
  }
}

async function loadCandles(): Promise<void> {
  try {
    const result = await api.candles(symbol.value, timeframe.value, 220)
    candles.value = result.candles
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : 'K 线加载失败'
  }
}

watch(timeframe, () => {
  void loadCandles()
})

onMounted(() => {
  void load()
})
</script>

<template>
  <section class="product-hero">
    <RouterLink class="back-link" to="/">← 返回产品列表</RouterLink>

    <div class="product-title">
      <span class="product-symbol large">{{ asset?.symbol ?? '—' }}</span>
      <div>
        <p class="eyebrow">Investment product</p>
        <h1>{{ asset?.name ?? symbol }}</h1>
        <p class="muted">
          {{ loading ? '加载中…' : instrumentLabel }}
          <span v-if="stream"> · {{ stream.name }} · {{ stream.status }}</span>
        </p>
      </div>
    </div>

    <div v-if="quote" class="quote-block">
      <strong class="quote-price">{{ fmt(quote.price, 2) }}</strong>
      <span class="quote-change" :class="change !== null && change >= 0 ? 'up' : 'down'">
        {{ fmtPercent(quote.change_24h_pct) }}
      </span>
      <span class="mono">{{ fmtTime(quote.market_time) }} · {{ quote.staleness }}</span>
    </div>

    <span class="status-pill" :class="{ active: stream }">
      {{ stream ? '已配置' : '待配置' }}
    </span>
  </section>

  <div v-if="!loading && !asset" class="panel empty-panel">
    <p class="eyebrow">Not found</p>
    <h2>还没有这个投资产品</h2>
    <p class="muted">当前库里只有 seed 的 BTC。P1 会加入资产与产品创建流程。</p>
  </div>

  <template v-else>
    <div class="tabs">
      <button class="tab active" type="button">概览</button>
      <button class="tab" type="button" disabled>对话 · P5</button>
      <button class="tab" type="button" disabled>配置 · P1</button>
    </div>

    <div v-if="!loading && !stream" class="banner">
      <strong>这个资产还没有投资产品</strong>
      <span>
        创建后才会启用监控、持仓与对话。
        <RouterLink :to="`/products/new?symbol=${symbol}`">创建投资产品</RouterLink>
      </span>
    </div>

    <section class="market-panel">
      <div class="market-head">
        <div>
          <p class="eyebrow">OKX · {{ quote?.instrument ?? 'market' }}</p>
          <h2>行情与指标</h2>
        </div>
        <div class="timeframe-switch">
          <button
            v-for="item in (['1h', '4h', '1d'] as Timeframe[])"
            :key="item"
            class="tf-button"
            :class="{ active: timeframe === item }"
            type="button"
            @click="timeframe = item"
          >
            {{ item.toUpperCase() }}
          </button>
        </div>
      </div>

      <p v-if="marketLoading" class="muted">正在拉取 OKX 行情…</p>
      <div v-else-if="error" class="market-error">
        <p class="error">{{ error }}</p>
        <button class="ghost-button" type="button" @click="loadMarket">重试</button>
      </div>

      <template v-else-if="quote">
        <div class="quote-stats">
          <div class="stat">
            <span>24h High</span>
            <strong>{{ fmt(quote.high_24h, 2) }}</strong>
          </div>
          <div class="stat">
            <span>24h Low</span>
            <strong>{{ fmt(quote.low_24h, 2) }}</strong>
          </div>
          <div class="stat">
            <span>24h Volume (USDT)</span>
            <strong>{{ fmt(quote.volume_24h, 0) }}</strong>
          </div>
          <div class="stat">
            <span>数据时间</span>
            <strong>{{ fmtTime(quote.fetched_at) }}</strong>
          </div>
        </div>

        <PriceChart :candles="candles" :timeframe="timeframe" />

        <div class="indicator-grid">
          <article
            v-for="[tf, snapshot] in indicatorEntries"
            :key="tf"
            class="indicator-card"
          >
            <header>
              <span class="card-kicker">{{ tf.toUpperCase() }}</span>
              <span class="trend" :class="String(snapshot.trend || 'unknown').toLowerCase()">
                {{ snapshot.trend ?? '—' }}
              </span>
            </header>
            <div class="indicator-row">
              <span>RSI14</span>
              <strong>{{ snapshot.rsi14 ?? '—' }}</strong>
            </div>
            <div class="indicator-row">
              <span>EMA20</span>
              <strong>{{ fmt(String(snapshot.ema20 ?? ''), 2) }}</strong>
            </div>
            <div class="indicator-row">
              <span>MACD Hist</span>
              <strong>{{ snapshot.macd_hist ?? '—' }}</strong>
            </div>
            <div class="indicator-row">
              <span>Volatility</span>
              <strong>{{ fmt(String(snapshot.volatility_pct ?? ''), 2) }}%</strong>
            </div>
          </article>
        </div>
      </template>
    </section>

    <section class="split-grid">
      <article v-if="derivative" class="card">
        <header class="card-head">
          <span class="card-kicker">Derivatives · observation</span>
          <span class="phase">{{ derivative.staleness }}</span>
        </header>
        <h2>{{ derivative.instrument }}</h2>
        <div class="derivative-grid">
          <div class="indicator-row">
            <span>Mark price</span>
            <strong>{{ fmt(derivative.mark_price, 2) }}</strong>
          </div>
          <div class="indicator-row">
            <span>Funding</span>
            <strong>{{ fmtFunding(derivative.funding_rate) }}</strong>
          </div>
          <div class="indicator-row">
            <span>Open interest (BTC)</span>
            <strong>{{ fmt(derivative.open_interest, 0) }}</strong>
          </div>
          <div class="indicator-row">
            <span>Next funding</span>
            <strong>{{ fmtTime(derivative.next_funding_time) }}</strong>
          </div>
        </div>
        <p class="muted">观察数据，不参与现货或合约持仓的盈亏计算。</p>
      </article>

      <article class="card">
        <header class="card-head">
          <span class="card-kicker">Position</span>
          <span class="phase">P2</span>
        </header>
        <h2>真实持仓</h2>
        <p class="muted">
          现货成交/修正 + USDT 本位永续持仓；用户录入清算价，本地算 uPnL、ROE 与距清算价距离。
        </p>
      </article>
    </section>

    <div class="placeholder-grid">
      <article class="card">
        <header class="card-head">
          <span class="card-kicker">Thesis</span>
          <span class="phase">P3</span>
        </header>
        <h2>投资论点</h2>
        <p class="muted">独立编辑器、AI 润色/整理、版本化与分级确认；旧版本可查。</p>
      </article>

      <article class="card">
        <header class="card-head">
          <span class="card-kicker">Conversation</span>
          <span class="phase">P5</span>
        </header>
        <h2>对话</h2>
        <p class="muted">只读盘问这个产品：价格、趋势、论点一致性、情景推演与情绪支持。</p>
      </article>
    </div>

    <p v-if="overview?.warnings.length" class="panel-note">
      {{ overview.warnings.join(' · ') }}
    </p>
  </template>
</template>