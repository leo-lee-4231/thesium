<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { api, type Asset, type Instrument, type Stream } from '@/api/client'
import BackButton from '@/components/BackButton.vue'

const route = useRoute()
const router = useRouter()

const assets = ref<Asset[]>([])
const existing = ref<Stream | null>(null)
const selectedSymbol = ref(String(route.query.symbol ?? 'BTC').toUpperCase())
const selectedInstrument = ref('')
const name = ref('')
const interval = ref(60)
const timezone = ref('Asia/Shanghai')
const agentEnabled = ref(true)
const loading = ref(true)
const submitting = ref(false)
const error = ref<string | null>(null)

const asset = computed(() => assets.value.find((item) => item.symbol === selectedSymbol.value))
const instruments = computed<Instrument[]>(() =>
  (asset.value?.instruments ?? []).filter((item) => item.market_type === 'SPOT'),
)

function defaultName(): string {
  return asset.value ? `${asset.value.name} 投资产品` : '投资产品'
}

function syncInstrument(): void {
  if (!instruments.value.some((item) => item.symbol === selectedInstrument.value)) {
    selectedInstrument.value = instruments.value[0]?.symbol ?? ''
  }
  if (!name.value || name.value.endsWith('投资产品')) {
    name.value = defaultName()
  }
}

onMounted(async () => {
  const [assetsResult, streamsResult] = await Promise.allSettled([api.assets(), api.streams()])
  if (assetsResult.status === 'fulfilled') {
    assets.value = assetsResult.value
    syncInstrument()
  } else {
    error.value = '无法加载资产目录'
  }
  if (streamsResult.status === 'fulfilled' && streamsResult.value.length > 0) {
    existing.value = streamsResult.value[0]
  }
  loading.value = false
})

async function submit(): Promise<void> {
  error.value = null
  const chosenAsset = asset.value
  const chosenInstrument = instruments.value.find((item) => item.symbol === selectedInstrument.value)
  if (!chosenAsset || !chosenInstrument) {
    error.value = '请选择资产与行情标的'
    return
  }
  if (!name.value.trim()) {
    error.value = '请填写产品名称'
    return
  }

  submitting.value = true
  try {
    await api.createStream({
      name: name.value.trim(),
      asset_symbol: chosenAsset.symbol,
      provider: chosenInstrument.provider,
      instrument_symbol: chosenInstrument.symbol,
      market_type: chosenInstrument.market_type === 'SWAP' ? 'SWAP' : 'SPOT',
      timezone: timezone.value,
      monitor_interval_minutes: interval.value,
      agent_enabled: agentEnabled.value,
    })
    await router.push(`/products/${chosenAsset.symbol.toLowerCase()}`)
  } catch (caught) {
    const message = caught instanceof Error ? caught.message : '创建失败'
    error.value = message.includes('STREAM_LIMIT')
      ? '已有一个 ACTIVE 投资产品。v1 只支持一个，先复用它。'
      : message
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <section class="product-hero">
    <BackButton fallback="/" />
    <div class="product-title">
      <span class="product-symbol large">＋</span>
      <div>
        <p class="eyebrow">New investment product</p>
        <h1>创建一个投资产品</h1>
        <p class="muted">选一个资产和行情标的；v1 只支持一个 ACTIVE 产品。</p>
      </div>
    </div>
  </section>

  <div v-if="existing" class="banner">
    <strong>已有一个 ACTIVE 投资产品：{{ existing.name }}</strong>
    <span>
      去
      <RouterLink :to="`/products/${existing.asset_symbol.toLowerCase()}`">产品详情</RouterLink>
      继续使用；v1 暂不支持同时创建第二个。
    </span>
  </div>

  <section class="form-card">
    <div v-if="loading" class="muted">正在加载资产目录…</div>

    <template v-else>
      <div class="form-grid">
        <label class="form-field">
          <span>资产</span>
          <select v-model="selectedSymbol" @change="syncInstrument">
            <option v-for="item in assets" :key="item.id" :value="item.symbol">
              {{ item.symbol }} · {{ item.name }} · {{ item.kind }}
            </option>
          </select>
          <small>v1 只有 BTC；ETH / 美股后续加入。</small>
        </label>

        <label class="form-field">
          <span>行情标的</span>
          <select v-model="selectedInstrument">
            <option v-for="item in instruments" :key="`${item.provider}-${item.symbol}`" :value="item.symbol">
              {{ item.provider.toUpperCase() }} · {{ item.symbol }} · {{ item.market_type }}
            </option>
          </select>
          <small>主标的用现货；SWAP 会作为同一产品的合约观察/持仓数据自动加载。</small>
        </label>

        <label class="form-field">
          <span>产品名称</span>
          <input v-model="name" type="text" maxlength="255" placeholder="例如：BTC 长期配置" />
        </label>

        <label class="form-field">
          <span>监控间隔</span>
          <select v-model.number="interval">
            <option :value="15">15 分钟</option>
            <option :value="30">30 分钟</option>
            <option :value="60">1 小时</option>
            <option :value="240">4 小时</option>
          </select>
          <small>定时分析频率；P4 才真正跑调度。</small>
        </label>

        <label class="form-field">
          <span>时区</span>
          <input v-model="timezone" type="text" placeholder="Asia/Shanghai" />
        </label>

        <label class="form-field checkbox">
          <input v-model="agentEnabled" type="checkbox" />
          <span>启用 Agent 分析</span>
        </label>
      </div>

      <p v-if="error" class="error">{{ error }}</p>

      <div class="form-actions">
        <RouterLink class="ghost-button" to="/">取消</RouterLink>
        <button
          class="primary-button"
          type="button"
          :disabled="submitting || Boolean(existing)"
          @click="submit"
        >
          {{ submitting ? '创建中…' : '创建投资产品' }}
        </button>
      </div>

      <p class="form-note">
        创建后会进入产品详情：行情、K 线、指标与合约观察已经可用；持仓、Thesis 和对话会按 P2/P3/P5 逐步接入。
      </p>
    </template>
  </section>
</template>