<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import {
  api,
  type Asset,
  type Decision,
  type Health,
  type MarketOverview,
  type Meta,
  type Portfolio,
  type Stream,
  type ThesisVersion,
} from '@/api/client'

const health = ref<Health | null>(null)
const meta = ref<Meta | null>(null)
const assets = ref<Asset[]>([])
const streams = ref<Stream[]>([])
const error = ref<string | null>(null)
const loading = ref(true)
const activeOverview = ref<MarketOverview | null>(null)
const activePortfolio = ref<Portfolio | null>(null)
const activeThesis = ref<ThesisVersion | null>(null)
const activeDecision = ref<Decision | null>(null)
const activeError = ref<string | null>(null)
const activeLoading = ref(false)

const apiOnline = computed(() => health.value?.status === 'ok')

const activeStream = computed(() => streams.value.find((stream) => stream.status === 'ACTIVE'))

function streamFor(symbol: string): Stream | undefined {
  return streams.value.find((stream) => stream.asset_symbol === symbol)
}

function fmt(value: string | null | undefined, digits = 2): string {
  if (value === null || value === undefined || value === '') return '—'
  const number = Number(value)
  if (!Number.isFinite(number)) return value
  return number.toLocaleString('en-US', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  })
}

function fmtPct(value: string | null | undefined): string {
  if (value === null || value === undefined || value === '') return '—'
  const number = Number(value)
  if (!Number.isFinite(number)) return '—'
  return `${number > 0 ? '+' : ''}${number.toFixed(2)}%`
}

function fmtTime(value: string | null | undefined): string {
  if (!value) return '—'
  return new Date(value).toLocaleString('zh-CN', {
    timeZone: 'Asia/Shanghai',
    hour12: false,
  })
}

async function loadActive(): Promise<void> {
  if (!activeStream.value) return
  activeLoading.value = true
  activeError.value = null
  const id = activeStream.value.id
  const symbol = activeStream.value.asset_symbol
  const [overviewResult, portfolioResult, thesisResult, decisionsResult] = await Promise.allSettled([
    api.marketOverview(symbol),
    api.portfolio(id),
    api.thesis(id),
    api.decisions(id),
  ])
  if (overviewResult.status === 'fulfilled') activeOverview.value = overviewResult.value
  if (portfolioResult.status === 'fulfilled') activePortfolio.value = portfolioResult.value
  if (thesisResult.status === 'fulfilled') activeThesis.value = thesisResult.value
  if (decisionsResult.status === 'fulfilled') activeDecision.value = decisionsResult.value[0] ?? null
  if (overviewResult.status === 'rejected') {
    activeError.value = '行情暂不可用；其他信息仍可查看。'
  }
  activeLoading.value = false
}

function instrumentLabel(asset: Asset): string {
  if (asset.instruments.length === 0) return '未配置行情'
  return asset.instruments
    .map((instrument) => `${instrument.provider.toUpperCase()} ${instrument.symbol} · ${instrument.market_type}`)
    .join(' / ')
}

async function load(): Promise<void> {
  loading.value = true
  error.value = null
  const [healthResult, metaResult, assetsResult, streamsResult] = await Promise.allSettled([
    api.health(),
    api.meta(),
    api.assets(),
    api.streams(),
  ])

  if (healthResult.status === 'fulfilled') health.value = healthResult.value
  if (metaResult.status === 'fulfilled') meta.value = metaResult.value
  if (assetsResult.status === 'fulfilled') assets.value = assetsResult.value
  if (streamsResult.status === 'fulfilled') streams.value = streamsResult.value

  const failures = [healthResult, metaResult, assetsResult, streamsResult].filter(
    (result) => result.status === 'rejected',
  )
  if (failures.length > 0 && health.value === null) {
    error.value = '无法连接 API。请确认后端已启动（默认 127.0.0.1:8000）。'
  }
  loading.value = false
  await loadActive()
}

onMounted(load)
</script>

<template>
  <section class="hero">
    <p class="eyebrow">Personal investment agent · self-hosted</p>
    <h1>
      让你的投资论点，<br />
      <em>经得起检验。</em>
    </h1>
    <p class="lede">
      记住你真实持有什么、原话怎么想。每次市场变化或改口，都给出一份可回放的收据。
    </p>
    <div class="hero-meta">
      <span class="chip">BTC 现货 + USDT 永续 · v1.0</span>
      <span class="chip">Thesis 版本化</span>
      <span class="chip">对话只读</span>
      <span class="chip">飞书 · v1.1</span>
    </div>
  </section>

  <section class="grid">
    <article class="card">
      <header class="card-head">
        <span class="card-kicker">Runtime</span>
        <span class="status-dot" :class="{ online: apiOnline }"></span>
      </header>
      <h2>{{ apiOnline ? 'API 在线' : 'API 未连接' }}</h2>
      <p v-if="health" class="muted">
        {{ health.app }} · v{{ health.version }} · {{ meta?.environment ?? 'unknown' }}
      </p>
      <p v-else class="muted">{{ loading ? '正在检查…' : '等待后端启动' }}</p>
      <p v-if="error" class="error">{{ error }}</p>
      <button class="ghost-button" type="button" @click="load">重新检查</button>
    </article>

    <article class="card">
      <header class="card-head">
        <span class="card-kicker">Investment products</span>
        <span class="count">{{ assets.length }}</span>
      </header>
      <h2>{{ assets.length === 0 ? '尚未配置投资产品' : '已关注资产' }}</h2>
      <p v-if="assets.length === 0" class="muted">
        下一步：把 BTC、ETH 或美股加进来，作为独立投资产品跟踪。
      </p>
      <ul v-else class="stream-list">
        <li v-for="asset in assets" :key="asset.id">
          <span>{{ asset.symbol }} · {{ asset.name }}</span>
          <span class="mono">{{ streamFor(asset.symbol)?.status ?? '待配置' }}</span>
        </li>
      </ul>
    </article>

    <article class="card">
      <header class="card-head">
        <span class="card-kicker">Phase</span>
        <span class="phase">{{ meta?.phase ?? 'P0' }}</span>
      </header>
      <h2>闭环已跑通</h2>
      <ul class="checklist">
        <li>OKX 现货 + SWAP 观察</li>
        <li>现货/永续持仓与风险快照</li>
        <li>Thesis 版本化 + AI 润色</li>
        <li>定时分析 + 通知策略 + 邮件</li>
        <li>Web 只读对话 + Run 回放</li>
      </ul>
    </article>
  </section>

  <section v-if="activeStream" class="panel dashboard-live">
    <div class="panel-head">
      <div>
        <p class="eyebrow">Live overview</p>
        <h2>{{ activeStream.asset_symbol }} · {{ activeStream.name }}</h2>
      </div>
      <div class="live-links">
        <RouterLink class="ghost-button small" :to="`/products/${activeStream.asset_symbol.toLowerCase()}`">
          概览
        </RouterLink>
        <RouterLink class="ghost-button small" :to="`/products/${activeStream.asset_symbol.toLowerCase()}/chat`">
          对话
        </RouterLink>
        <RouterLink class="ghost-button small" :to="`/products/${activeStream.asset_symbol.toLowerCase()}/thesis`">
          Thesis
        </RouterLink>
      </div>
    </div>

    <p v-if="activeLoading" class="muted">加载当前产品…</p>
    <p v-if="activeError" class="error">{{ activeError }}</p>

    <div v-if="activeOverview" class="live-grid">
      <div class="live-card">
        <span>现货价格</span>
        <strong>{{ fmt(activeOverview.quote.price) }}</strong>
        <small>
          24h {{ fmtPct(activeOverview.quote.change_24h_pct) }} ·
          {{ activeOverview.quote.staleness }} · {{ fmtTime(activeOverview.quote.market_time) }}
        </small>
      </div>
      <div class="live-card">
        <span>最新建议</span>
        <strong>{{ activeDecision?.decision ?? '—' }}</strong>
        <small>
          {{ activeDecision ? `${activeDecision.priority} · ${fmtTime(activeDecision.created_at)}` : '还没有分析' }}
        </small>
      </div>
      <div class="live-card">
        <span>ACTIVE Thesis</span>
        <strong>{{ activeThesis ? `v${activeThesis.version}` : '未写' }}</strong>
        <small>{{ activeThesis ? activeThesis.change_class : '—' }} · 用户确认后生效</small>
      </div>
      <div class="live-card">
        <span>持仓</span>
        <strong>{{ activePortfolio ? fmt(activePortfolio.spot.state.quantity, 4) : '—' }}</strong>
        <small>
          现货 {{ activeStream.asset_symbol }} · 永续
          {{ activePortfolio?.derivative ? activePortfolio.derivative.state.side : '无' }}
        </small>
      </div>
    </div>

    <p v-if="activeDecision" class="live-summary">{{ activeDecision.summary }}</p>
    <p class="form-note">
      数字来自本地数据库与 OKX 公共行情；建议绑定当时的 Thesis、持仓快照与行情时间戳，可在产品页回放。
    </p>
  </section>

  <section class="products">
    <div class="products-head">
      <div>
        <p class="eyebrow">Investment products</p>
        <h2>你关注的资产</h2>
      </div>
      <span class="mono">v1.0 · BTC 现货；ETH / 美股后续</span>
    </div>

    <div class="product-grid">
      <RouterLink
        v-for="asset in assets"
        :key="asset.id"
        class="product-card"
        :to="`/products/${asset.symbol.toLowerCase()}`"
      >
        <div class="product-top">
          <span class="product-symbol">{{ asset.symbol }}</span>
          <span class="status-pill" :class="{ active: streamFor(asset.symbol) }">
            {{ streamFor(asset.symbol) ? '已配置' : '待配置' }}
          </span>
        </div>
        <h3>{{ asset.name }}</h3>
        <p class="muted">{{ instrumentLabel(asset) }}</p>
        <div class="product-foot">
          <span>{{ streamFor(asset.symbol)?.name ?? '创建投资产品' }}</span>
          <span class="arrow">→</span>
        </div>
      </RouterLink>

      <RouterLink v-if="streams.length === 0" class="product-card ghost" to="/products/new">
        <div class="product-top">
          <span class="product-symbol">＋</span>
          <span class="status-pill">新建</span>
        </div>
        <h3>创建投资产品</h3>
        <p class="muted">选资产、行情标的与监控间隔；创建后在这张卡里查看、对话、配置。</p>
        <div class="product-foot">
          <span>v1 只支持一个 ACTIVE 产品</span>
          <span class="arrow">→</span>
        </div>
      </RouterLink>
    </div>
  </section>

  <section class="panel">
    <div class="panel-head">
      <div>
        <p class="eyebrow">v1.0 scope</p>
        <h2>先把闭环跑通，再加第二入口</h2>
      </div>
      <span class="mono">BTC · Spot + Swap · 1h/4h/1d</span>
    </div>
    <div class="scope-grid">
      <div>
        <h3>核心闭环</h3>
        <p>行情 → 持仓 → Thesis 版本 → 定时分析 → Decision → 通知</p>
      </div>
      <div>
        <h3>Web 对话</h3>
        <p>只读盘问 Thesis：价格、趋势、论点一致性、情景推演与情绪支持</p>
      </div>
      <div>
        <h3>可追溯</h3>
        <p>每次分析固定 Thesis 版本、持仓快照、行情时间戳与模型</p>
      </div>
    </div>
    <p class="panel-note">
      通知只发重要变化：类别跃迁、HIGH/URGENT、论点冲突、风险预算突破。普通 WAIT/HOLD 不打扰；
      所有建议都可在 Web 里回放当时的 Thesis、持仓与行情。
    </p>
  </section>
</template>