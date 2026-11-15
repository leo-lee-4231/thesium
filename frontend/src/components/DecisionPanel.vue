<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { api, type Decision } from '@/api/client'

const props = defineProps<{ streamId: string }>()

const decisions = ref<Decision[]>([])
const analyzing = ref(false)
const loading = ref(true)
const error = ref<string | null>(null)
const notice = ref<string | null>(null)

const latest = computed(() => decisions.value[0] ?? null)
const llmMissing = computed(() => (error.value ?? '').includes('LLM_NOT_CONFIGURED'))
const marketUnavailable = computed(() => (error.value ?? '').includes('MARKET_UNAVAILABLE'))
const rateLimited = computed(() => (error.value ?? '').includes('RATE_LIMITED'))

function fmtDate(value: string): string {
  return new Date(value).toLocaleString('zh-CN', {
    timeZone: 'Asia/Shanghai',
    hour12: false,
  })
}

function decisionClass(value: string): string {
  return value.toLowerCase()
}

async function load(): Promise<void> {
  loading.value = true
  error.value = null
  try {
    decisions.value = await api.decisions(props.streamId)
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : '分析记录加载失败'
  } finally {
    loading.value = false
  }
}

async function analyze(): Promise<void> {
  analyzing.value = true
  error.value = null
  notice.value = null
  try {
    const result = await api.analyze(props.streamId)
    decisions.value = [result.decision, ...decisions.value]
    notice.value = `分析完成 · ${result.run.latency_ms ?? '—'} ms · ${result.run.model ?? 'model'}`
    window.dispatchEvent(new CustomEvent('thesium:notifications-changed'))
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : '分析失败'
  } finally {
    analyzing.value = false
  }
}

onMounted(() => {
  void load()
})
</script>

<template>
  <section class="decision-panel">
    <div class="market-head">
      <div>
        <p class="eyebrow">Agent · Decision</p>
        <h2>分析建议</h2>
      </div>
      <button class="primary-button" type="button" :disabled="analyzing" @click="analyze">
        {{ analyzing ? '分析中…' : '立即分析' }}
      </button>
    </div>

    <p class="muted decision-hint">
      调用已配置的 LLM 读取 Thesis、行情、指标与持仓；可能需要 10–60 秒。结果会保存为可回放的 Decision。
    </p>

    <p v-if="error" class="error">
      {{ error }}
      <RouterLink v-if="llmMissing" class="inline-link" to="/settings">去 Settings 配置 LLM</RouterLink>
    </p>
    <p v-if="rateLimited" class="error-hint">
      OKX 公共接口在限流（HTTP 429 或 code 50011）。等待约 1 分钟后重试；这不是 LLM 或 Thesis 的问题。
    </p>
    <p v-else-if="marketUnavailable" class="error-hint">
      OKX 行情不可达。常见原因是本机代理 127.0.0.1:7897 短暂断开或网络波动；当前网络下 OKX 直连不可用。
      稍后点「立即分析」重试；LLM 与 Thesis 未受影响。
    </p>
    <p v-if="notice" class="notice">{{ notice }}</p>

    <p v-if="loading" class="muted">加载分析记录…</p>
    <p v-else-if="!latest" class="muted">
      还没有分析记录。先写好 Thesis，再点「立即分析」。
    </p>

    <article v-if="latest" class="decision-card">
      <header class="decision-head">
        <span class="decision-badge" :class="decisionClass(latest.decision)">{{ latest.decision }}</span>
        <span class="priority-chip">{{ latest.priority }}</span>
        <span class="mono">confidence {{ Number(latest.confidence).toFixed(2) }}（非胜率）</span>
        <RouterLink class="mono inline-link" :to="`/runs/${latest.agent_run_id}`">
          Run 详情 →
        </RouterLink>
        <span class="mono decision-time">{{ fmtDate(latest.created_at) }}</span>
      </header>

      <p class="decision-summary">{{ latest.summary }}</p>

      <div class="decision-meta">
        <div>
          <span>Thesis</span>
          <strong>{{ latest.thesis_alignment.status }}</strong>
        </div>
        <div>
          <span>数据质量</span>
          <strong>{{ latest.data_quality.status }} / {{ latest.data_quality.staleness }}</strong>
        </div>
        <div>
          <span>仓位影响</span>
          <strong>{{ latest.position_impact.assessment }}</strong>
        </div>
        <div>
          <span>通知建议</span>
          <strong>{{ latest.notification_recommendation.notify ? '建议通知' : '不通知' }}</strong>
        </div>
      </div>

      <p v-if="latest.thesis_alignment.explanation" class="muted">
        {{ latest.thesis_alignment.explanation }}
      </p>

      <div v-if="latest.derivative_recommendation" class="derivative-plan">
        <header>
          <span class="card-kicker">Perpetual</span>
          <strong>{{ latest.derivative_recommendation.action }}</strong>
        </header>
        <p class="muted">{{ latest.derivative_recommendation.rationale }}</p>
        <div v-if="latest.derivative_recommendation.stop_loss" class="stop-loss-box">
          <span>止损 {{ latest.derivative_recommendation.stop_loss.price }}</span>
          <span class="mono">
            {{ latest.derivative_recommendation.stop_loss.source }} ·
            risk {{ latest.derivative_recommendation.stop_loss.risk_pct_equity ?? '—' }}%
          </span>
          <span
            v-for="warning in latest.derivative_recommendation.stop_loss.warnings"
            :key="warning"
            class="warning-inline"
          >
            {{ warning }}
          </span>
        </div>
      </div>

      <div class="evidence-grid">
        <div>
          <h3>支持证据</h3>
          <ul>
            <li v-for="item in latest.evidence_for" :key="item.claim">
              {{ item.claim }}
              <span class="mono">{{ item.as_of ?? '' }}</span>
            </li>
          </ul>
        </div>
        <div>
          <h3>反面证据</h3>
          <ul>
            <li v-for="item in latest.evidence_against" :key="item.claim">
              {{ item.claim }}
              <span class="mono">{{ item.as_of ?? '' }}</span>
            </li>
          </ul>
        </div>
      </div>
    </article>

    <details v-if="decisions.length > 1" class="decision-history">
      <summary>历史分析（{{ decisions.length }}）</summary>
      <ul>
        <li v-for="item in decisions.slice(1, 8)" :key="item.id">
          <span class="decision-badge small" :class="decisionClass(item.decision)">{{ item.decision }}</span>
          <span>{{ item.priority }}</span>
          <span class="muted">{{ item.summary.slice(0, 72) }}</span>
          <span class="mono">{{ fmtDate(item.created_at) }}</span>
        </li>
      </ul>
    </details>
  </section>
</template>