<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'

import { api, type Asset, type Stream } from '@/api/client'

const route = useRoute()
const assets = ref<Asset[]>([])
const streams = ref<Stream[]>([])
const loading = ref(true)

const symbol = computed(() => String(route.params.symbol ?? '').toUpperCase())
const asset = computed(() => assets.value.find((item) => item.symbol === symbol.value))
const stream = computed(() => streams.value.find((item) => item.asset_symbol === symbol.value))

const instrumentLabel = computed(() => {
  if (!asset.value || asset.value.instruments.length === 0) return '行情未配置'
  return asset.value.instruments
    .map((instrument) => `${instrument.provider.toUpperCase()} ${instrument.symbol} · ${instrument.market_type}`)
    .join(' / ')
})

onMounted(async () => {
  const [assetsResult, streamsResult] = await Promise.allSettled([api.assets(), api.streams()])
  if (assetsResult.status === 'fulfilled') assets.value = assetsResult.value
  if (streamsResult.status === 'fulfilled') streams.value = streamsResult.value
  loading.value = false
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

    <div class="placeholder-grid">
      <article class="card">
        <header class="card-head">
          <span class="card-kicker">Market</span>
          <span class="phase">P1</span>
        </header>
        <h2>行情与指标</h2>
        <p class="muted">公共行情：现货 + 合约观察（mark price / funding / open interest），1h/4h/1d K 线。</p>
      </article>

      <article class="card">
        <header class="card-head">
          <span class="card-kicker">Position</span>
          <span class="phase">P2</span>
        </header>
        <h2>真实持仓</h2>
        <p class="muted">现货成交/修正 + USDT 本位永续持仓；用户录入清算价，本地算 uPnL、ROE 与距清算价距离。</p>
      </article>

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
  </template>
</template>