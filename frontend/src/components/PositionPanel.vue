<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import {
  api,
  type DerivativeEvent,
  type DerivativeEventInput,
  type Portfolio,
  type PositionEvent,
  type SpotEventInput,
} from '@/api/client'

const props = defineProps<{
  streamId: string
  symbol: string
}>()

const tab = ref<'spot' | 'perp'>('spot')
const portfolio = ref<Portfolio | null>(null)
const spotEvents = ref<PositionEvent[]>([])
const derivativeEvents = ref<DerivativeEvent[]>([])
const loading = ref(true)
const submitting = ref(false)
const error = ref<string | null>(null)

const spotKind = ref<'BUY' | 'SELL' | 'OPENING' | 'CORRECTION'>('BUY')
const spotQty = ref('0.01')
const spotPrice = ref('')
const spotFee = ref('0')
const spotTime = ref(localNow())
const spotNote = ref('')

const perpKind = ref<
  'OPEN' | 'INCREASE' | 'REDUCE' | 'CLOSE' | 'ADJUST_MARGIN' | 'CORRECTION'
>('OPEN')
const perpSide = ref<'LONG' | 'SHORT'>('LONG')
const perpQty = ref('0.01')
const perpPrice = ref('')
const perpLeverage = ref('3')
const perpMargin = ref('')
const perpLiq = ref('')
const perpFee = ref('0')
const perpMarginDelta = ref('')
const perpTime = ref(localNow())
const perpNote = ref('')

const spot = computed(() => portfolio.value?.spot ?? null)
const perp = computed(() => portfolio.value?.derivative ?? null)
const liqDanger = computed(() => {
  const value = perp.value?.metrics.liq_distance_pct
  return value !== null && value !== undefined && Number(value) < 10
})

function localNow(): string {
  const date = new Date()
  return new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 16)
}

function toIso(value: string): string {
  return new Date(value).toISOString()
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

function pct(value: string | null | undefined): string {
  if (value === null || value === undefined) return '—'
  const number = Number(value)
  if (!Number.isFinite(number)) return '—'
  return `${number > 0 ? '+' : ''}${number.toFixed(2)}%`
}

function fmtTime(value: string): string {
  return new Date(value).toLocaleString('zh-CN', {
    timeZone: 'Asia/Shanghai',
    hour12: false,
  })
}

async function load(): Promise<void> {
  loading.value = true
  error.value = null
  try {
    const [portfolioResult, spotEventResult, derivativeEventResult] = await Promise.all([
      api.portfolio(props.streamId),
      api.spotEvents(props.streamId),
      api.derivativeEvents(props.streamId),
    ])
    portfolio.value = portfolioResult
    spotEvents.value = spotEventResult.slice(0, 5)
    derivativeEvents.value = derivativeEventResult.slice(0, 5)
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : '持仓加载失败'
  } finally {
    loading.value = false
  }
}

async function submitSpot(): Promise<void> {
  submitting.value = true
  error.value = null
  try {
    const payload: SpotEventInput = {
      kind: spotKind.value,
      quantity: spotQty.value,
      fee: spotFee.value || '0',
      occurred_at: toIso(spotTime.value),
      note: spotNote.value || undefined,
    }
    if (spotKind.value === 'BUY' || spotKind.value === 'SELL') {
      payload.price = spotPrice.value
    } else {
      payload.avg_cost = spotPrice.value
    }
    await api.createSpotEvent(props.streamId, payload)
    spotNote.value = ''
    await load()
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : '现货事件提交失败'
  } finally {
    submitting.value = false
  }
}

function buildDerivativePayload(): DerivativeEventInput {
  const payload: DerivativeEventInput = {
    kind: perpKind.value,
    side: perpSide.value,
    occurred_at: toIso(perpTime.value),
    fee: perpFee.value || '0',
    note: perpNote.value || undefined,
    margin_mode: 'ISOLATED',
  }
  if (['OPEN', 'INCREASE', 'REDUCE', 'CORRECTION'].includes(perpKind.value)) {
    payload.quantity_base = perpQty.value
    payload.price = perpPrice.value
  }
  if (['OPEN', 'CORRECTION'].includes(perpKind.value)) {
    payload.leverage = perpLeverage.value
    payload.margin = perpMargin.value
    payload.liquidation_price = perpLiq.value || undefined
  }
  if (perpKind.value === 'OPEN' && !perpMargin.value) {
    throw new Error('开仓需要填写保证金')
  }
  if (perpKind.value === 'OPEN' && !perpLiq.value) {
    // 允许为空，但 UI 明确提示
  }
  if (perpKind.value === 'INCREASE') {
    payload.margin_delta = perpMarginDelta.value || undefined
  }
  if (perpKind.value === 'REDUCE') {
    payload.margin = perpMargin.value || undefined
  }
  if (perpKind.value === 'CLOSE') {
    payload.price = perpPrice.value
  }
  if (perpKind.value === 'ADJUST_MARGIN') {
    payload.margin = perpMargin.value
  }
  return payload
}

async function submitDerivative(): Promise<void> {
  submitting.value = true
  error.value = null
  try {
    const payload = buildDerivativePayload()
    await api.createDerivativeEvent(props.streamId, payload)
    perpNote.value = ''
    await load()
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : '永续事件提交失败'
  } finally {
    submitting.value = false
  }
}

onMounted(() => {
  void load()
})
</script>

<template>
  <section class="position-panel">
    <div class="market-head">
      <div>
        <p class="eyebrow">Portfolio · {{ symbol }}</p>
        <h2>真实持仓</h2>
      </div>
      <div class="timeframe-switch">
        <button class="tf-button" :class="{ active: tab === 'spot' }" type="button" @click="tab = 'spot'">
          SPOT
        </button>
        <button class="tf-button" :class="{ active: tab === 'perp' }" type="button" @click="tab = 'perp'">
          PERP
        </button>
      </div>
    </div>

    <p v-if="loading" class="muted">正在加载持仓…</p>
    <p v-if="error" class="error">{{ error }}</p>

    <div v-if="portfolio && !loading" class="position-grid">
      <article v-if="tab === 'spot'" class="position-card">
        <header>
          <span class="card-kicker">Spot</span>
          <span class="phase">v{{ spot?.version ?? 0 }}</span>
        </header>
        <h3>{{ fmt(spot?.state.quantity, 8) }} BTC</h3>
        <div class="indicator-row">
          <span>成本均价</span>
          <strong>{{ fmt(spot?.state.avg_cost, 2) }}</strong>
        </div>
        <div class="indicator-row">
          <span>已实现盈亏</span>
          <strong :class="{ 'pnl-up': Number(spot?.state.realized_pnl) >= 0, 'pnl-down': Number(spot?.state.realized_pnl) < 0 }">
            {{ fmt(spot?.state.realized_pnl, 2) }}
          </strong>
        </div>
        <div class="indicator-row">
          <span>市值</span>
          <strong>{{ fmt(spot?.metrics.market_value, 2) }}</strong>
        </div>
        <div class="indicator-row">
          <span>浮动盈亏</span>
          <strong :class="{ 'pnl-up': Number(spot?.metrics.unrealized_pnl) >= 0, 'pnl-down': Number(spot?.metrics.unrealized_pnl) < 0 }">
            {{ fmt(spot?.metrics.unrealized_pnl, 2) }} · {{ pct(spot?.metrics.unrealized_pnl_pct) }}
          </strong>
        </div>
        <p class="muted">标记价 {{ fmt(spot?.metrics.mark_price, 2) }} · 快照 v{{ spot?.version }}</p>
      </article>

      <article v-else class="position-card">
        <header>
          <span class="card-kicker">Perpetual · USDT</span>
          <span class="phase">v{{ perp?.version ?? 0 }}</span>
        </header>
        <template v-if="perp">
          <h3>
            {{ perp.state.side }} {{ fmt(perp.state.quantity_base, 6) }} BTC
            <span class="leverage-pill">{{ fmt(perp.state.leverage, 1) }}x</span>
          </h3>
          <div class="indicator-row">
            <span>开仓均价</span>
            <strong>{{ fmt(perp.state.entry_price, 2) }}</strong>
          </div>
          <div class="indicator-row">
            <span>保证金</span>
            <strong>{{ fmt(perp.state.margin, 2) }}</strong>
          </div>
          <div class="indicator-row">
            <span>清算价（用户输入）</span>
            <strong>{{ fmt(perp.state.liquidation_price, 2) }}</strong>
          </div>
          <div class="indicator-row">
            <span>uPnL / ROE</span>
            <strong :class="{ 'pnl-up': Number(perp.metrics.unrealized_pnl) >= 0, 'pnl-down': Number(perp.metrics.unrealized_pnl) < 0 }">
              {{ fmt(perp.metrics.unrealized_pnl, 2) }} · {{ pct(perp.metrics.roe) }}
            </strong>
          </div>
          <div class="indicator-row">
            <span>距清算价</span>
            <strong :class="{ danger: liqDanger }">{{ pct(perp.metrics.liq_distance_pct) }}</strong>
          </div>
          <div class="indicator-row">
            <span>标记价</span>
            <strong>{{ fmt(perp.metrics.mark_price, 2) }}</strong>
          </div>
        </template>
        <p v-else class="muted">还没有永续持仓。用右侧表单开多/开空。</p>
      </article>

      <form v-if="tab === 'spot'" class="position-form" @submit.prevent="submitSpot">
        <p class="card-kicker">记录现货</p>
        <label class="form-field">
          <span>类型</span>
          <select v-model="spotKind">
            <option value="BUY">买入</option>
            <option value="SELL">卖出</option>
            <option value="CORRECTION">修正持仓</option>
            <option value="OPENING">初始持仓</option>
          </select>
        </label>
        <label class="form-field">
          <span>数量（BTC）</span>
          <input v-model="spotQty" type="text" inputmode="decimal" />
        </label>
        <label class="form-field">
          <span>{{ spotKind === 'CORRECTION' || spotKind === 'OPENING' ? '成本均价' : '成交价' }}</span>
          <input v-model="spotPrice" type="text" inputmode="decimal" placeholder="USDT" />
        </label>
        <label class="form-field">
          <span>手续费</span>
          <input v-model="spotFee" type="text" inputmode="decimal" />
        </label>
        <label class="form-field">
          <span>成交时间</span>
          <input v-model="spotTime" type="datetime-local" />
        </label>
        <button class="primary-button" type="submit" :disabled="submitting">
          {{ submitting ? '提交中…' : '记录现货事件' }}
        </button>
      </form>

      <form v-else class="position-form" @submit.prevent="submitDerivative">
        <p class="card-kicker">记录永续</p>
        <label class="form-field">
          <span>动作</span>
          <select v-model="perpKind">
            <option value="OPEN">开仓</option>
            <option value="INCREASE">加仓</option>
            <option value="REDUCE">减仓</option>
            <option value="CLOSE">平仓</option>
            <option value="ADJUST_MARGIN">调整保证金</option>
            <option value="CORRECTION">修正持仓</option>
          </select>
        </label>
        <label class="form-field">
          <span>方向</span>
          <select v-model="perpSide">
            <option value="LONG">LONG</option>
            <option value="SHORT">SHORT</option>
          </select>
        </label>
        <label v-if="perpKind !== 'ADJUST_MARGIN'" class="form-field">
          <span>数量（BTC）</span>
          <input v-model="perpQty" type="text" inputmode="decimal" />
        </label>
        <label v-if="perpKind !== 'ADJUST_MARGIN'" class="form-field">
          <span>成交价</span>
          <input v-model="perpPrice" type="text" inputmode="decimal" placeholder="USDT" />
        </label>
        <label v-if="perpKind === 'OPEN' || perpKind === 'CORRECTION'" class="form-field">
          <span>杠杆</span>
          <input v-model="perpLeverage" type="text" inputmode="decimal" />
        </label>
        <label v-if="perpKind !== 'INCREASE' && perpKind !== 'CLOSE'" class="form-field">
          <span>保证金</span>
          <input v-model="perpMargin" type="text" inputmode="decimal" placeholder="USDT" />
        </label>
        <label v-if="perpKind === 'OPEN' || perpKind === 'CORRECTION'" class="form-field">
          <span>清算价（用户输入）</span>
          <input v-model="perpLiq" type="text" inputmode="decimal" placeholder="交易软件显示值" />
        </label>
        <label v-if="perpKind === 'INCREASE'" class="form-field">
          <span>追加保证金</span>
          <input v-model="perpMarginDelta" type="text" inputmode="decimal" />
        </label>
        <label class="form-field">
          <span>手续费</span>
          <input v-model="perpFee" type="text" inputmode="decimal" />
        </label>
        <label class="form-field">
          <span>成交时间</span>
          <input v-model="perpTime" type="datetime-local" />
        </label>
        <button class="primary-button" type="submit" :disabled="submitting">
          {{ submitting ? '提交中…' : '记录永续事件' }}
        </button>
      </form>
    </div>

    <div v-if="spotEvents.length || derivativeEvents.length" class="event-lists">
      <details>
        <summary>最近现货事件（{{ spotEvents.length }}）</summary>
        <ul>
          <li v-for="event in spotEvents" :key="event.id">
            <span>{{ event.kind }}</span>
            <span class="mono">{{ fmt(event.quantity, 6) }} @ {{ fmt(event.price, 2) }}</span>
            <span class="mono">{{ fmtTime(event.occurred_at) }}</span>
          </li>
        </ul>
      </details>
      <details>
        <summary>最近永续事件（{{ derivativeEvents.length }}）</summary>
        <ul>
          <li v-for="event in derivativeEvents" :key="event.id">
            <span>{{ event.kind }} · {{ event.side }}</span>
            <span class="mono">{{ fmt(event.quantity_base, 6) }} @ {{ fmt(event.price, 2) }}</span>
            <span class="mono">{{ fmtTime(event.occurred_at) }}</span>
          </li>
        </ul>
      </details>
    </div>

    <p v-if="portfolio?.warnings.length" class="panel-note">
      {{ portfolio.warnings.join(' · ') }}
    </p>
  </section>
</template>