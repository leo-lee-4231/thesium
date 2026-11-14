<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { api, type Asset, type Health, type Meta, type Stream } from '@/api/client'

const health = ref<Health | null>(null)
const meta = ref<Meta | null>(null)
const assets = ref<Asset[]>([])
const streams = ref<Stream[]>([])
const error = ref<string | null>(null)
const loading = ref(true)

const apiOnline = computed(() => health.value?.status === 'ok')

function streamFor(symbol: string): Stream | undefined {
  return streams.value.find((stream) => stream.asset_symbol === symbol)
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
      <h2>骨架已就位</h2>
      <ul class="checklist">
        <li>FastAPI + 健康检查</li>
        <li>Postgres + Alembic 初始迁移</li>
        <li>Worker 进程骨架</li>
        <li>Vue 3 + Vite 壳</li>
        <li>Docker Compose 一键启动</li>
      </ul>
    </article>
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
      下一步 P1：接入 OKX 公共行情（现货 + 合约观察），回填 K 线并计算基础指标。
    </p>
  </section>
</template>