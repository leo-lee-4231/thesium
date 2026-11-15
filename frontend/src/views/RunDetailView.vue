<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'

import { api, type AgentRun } from '@/api/client'

const route = useRoute()
const run = ref<AgentRun | null>(null)
const loading = ref(true)
const error = ref<string | null>(null)

const backTo = computed(() => {
  if (!streamInfo.value.symbol) return '/'
  const base = `/products/${streamInfo.value.symbol.toLowerCase()}`
  return run.value?.task_type === 'CHAT' ? `${base}/chat` : base
})

const streamInfo = computed(() => {
  const context = run.value?.input_context as
    | { stream?: { id?: string; name?: string }; asset?: { symbol?: string } }
    | null
    | undefined
  return {
    id: context?.stream?.id ?? run.value?.stream_id ?? '',
    name: context?.stream?.name ?? '投资产品',
    symbol: context?.asset?.symbol ?? '',
  }
})

function fmtDate(value: string | null): string {
  if (!value) return '—'
  return new Date(value).toLocaleString('zh-CN', {
    timeZone: 'Asia/Shanghai',
    hour12: false,
  })
}

function pretty(value: unknown): string {
  return JSON.stringify(value, null, 2)
}

async function load(): Promise<void> {
  loading.value = true
  error.value = null
  try {
    run.value = await api.agentRun(String(route.params.runId))
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : 'Run 加载失败'
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  void load()
})
</script>

<template>
  <section class="product-hero">
    <RouterLink v-if="streamInfo.symbol" class="back-link" :to="backTo">
      ← 返回 {{ streamInfo.symbol }} {{ run?.task_type === 'CHAT' ? '对话' : '概览' }}
    </RouterLink>
    <div class="product-title">
      <span class="product-symbol large">R</span>
      <div>
        <p class="eyebrow">Agent Run · audit</p>
        <h1>Run 详情</h1>
        <p class="muted">固定当时的 Thesis / 持仓 / 行情快照、模型与工具来源，可回放。</p>
      </div>
    </div>
    <span v-if="run" class="status-pill" :class="{ active: run.status === 'SUCCEEDED' }">
      {{ run.status }}
    </span>
  </section>

  <p v-if="loading" class="muted">加载 Run…</p>
  <p v-if="error" class="error">{{ error }}</p>

  <template v-if="run">
    <section class="panel">
      <div class="settings-status">
        <div>
          <span>任务</span>
          <strong>{{ run.task_type }}</strong>
        </div>
        <div>
          <span>模型</span>
          <strong>{{ run.model ?? '—' }}</strong>
        </div>
        <div>
          <span>Prompt</span>
          <strong>{{ run.prompt_version }}</strong>
        </div>
        <div>
          <span>耗时</span>
          <strong>{{ run.latency_ms ?? '—' }} ms</strong>
        </div>
        <div>
          <span>开始</span>
          <strong>{{ fmtDate(run.started_at) }}</strong>
        </div>
        <div>
          <span>结束</span>
          <strong>{{ fmtDate(run.finished_at) }}</strong>
        </div>
        <div>
          <span>Thesis 版本</span>
          <strong class="mono">{{ run.thesis_version_id ?? '—' }}</strong>
        </div>
        <div>
          <span>行情快照</span>
          <strong class="mono">{{ run.market_snapshot_id ?? '—' }}</strong>
        </div>
        <div>
          <span>持仓快照</span>
          <strong class="mono">{{ run.position_snapshot_id ?? '—' }}</strong>
        </div>
        <div>
          <span>永续快照</span>
          <strong class="mono">{{ run.derivative_snapshot_id ?? '—' }}</strong>
        </div>
      </div>

      <p v-if="run.error_code" class="error">
        {{ run.error_code }} · {{ run.error_message }}
      </p>

      <details v-if="run.tool_calls.length" class="run-details" open>
        <summary>工具 / 来源（{{ run.tool_calls.length }}）</summary>
        <ul class="run-source-list">
          <li v-for="source in run.tool_calls" :key="source.tool">
            <span class="mono">{{ source.tool }}</span>
            <span>{{ source.label }}</span>
            <span class="muted">{{ source.as_of ?? '—' }}</span>
          </li>
        </ul>
      </details>

      <details v-if="run.output_parsed" class="run-details" open>
        <summary>输出</summary>
        <pre class="run-json">{{ pretty(run.output_parsed) }}</pre>
      </details>

      <details v-if="run.input_context" class="run-details">
        <summary>输入上下文（含 Thesis / 持仓 / 行情）</summary>
        <pre class="run-json">{{ pretty(run.input_context) }}</pre>
      </details>
    </section>
  </template>
</template>