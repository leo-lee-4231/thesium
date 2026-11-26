<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { api, type OpsStatus, type RetentionSettings } from '@/api/client'
import BackButton from '@/components/BackButton.vue'

const status = ref<OpsStatus | null>(null)
const loading = ref(true)
const error = ref<string | null>(null)
const digestRunning = ref(false)
const digestMessage = ref<string | null>(null)
const digestError = ref<string | null>(null)
const retentionSettings = ref<RetentionSettings | null>(null)
const retentionSaving = ref(false)
const retentionMessage = ref<string | null>(null)
const retentionError = ref<string | null>(null)
const retentionDraft = ref({
  enabled: true,
  candle_1h_days: 365,
  candle_4h_days: 730,
  candle_1d_days: 1825,
  snapshot_days: 90,
})

const stream = computed(() => status.value?.stream ?? null)
const digest = computed(() => status.value?.daily_digest ?? null)
const retention = computed(() => status.value?.maintenance.market_retention ?? null)

function syncRetentionDraft(value: RetentionSettings): void {
  retentionDraft.value = {
    enabled: value.enabled,
    candle_1h_days: value.candle_1h_days,
    candle_4h_days: value.candle_4h_days,
    candle_1d_days: value.candle_1d_days,
    snapshot_days: value.snapshot_days,
  }
}

function fmt(value: string | null | undefined): string {
  if (!value) return '—'
  return new Date(value).toLocaleString('zh-CN', {
    timeZone: 'Asia/Shanghai',
    hour12: false,
  })
}

function counts(value: Record<string, number> | undefined): string {
  if (!value) return '无'
  const entries = Object.entries(value).filter(([, count]) => count > 0)
  if (entries.length === 0) return '无'
  return entries.map(([key, count]) => `${key} ${count}`).join(' · ')
}

function statusClass(value: string | null | undefined): string {
  if (!value) return ''
  if (['SUCCEEDED', 'SENT', 'ACTIVE', 'FRESH'].includes(value)) return 'ok'
  if (['FAILED', 'URGENT', 'STALE'].includes(value)) return 'bad'
  if (['PENDING', 'RUNNING', 'RETRYING', 'DEGRADED'].includes(value)) return 'warn'
  return ''
}

async function load(): Promise<void> {
  loading.value = true
  error.value = null
  try {
    status.value = await api.opsStatus()
    try {
      retentionSettings.value = await api.retentionStatus()
    } catch {
      retentionSettings.value = status.value.maintenance.market_retention
    }
    if (retentionSettings.value) syncRetentionDraft(retentionSettings.value)
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : '系统状态加载失败'
  } finally {
    loading.value = false
  }
}

async function runDigest(): Promise<void> {
  if (!stream.value || digestRunning.value) return
  if (!window.confirm('将立即跑一次分析并发送日报，可能需要 30–60 秒。继续？')) return
  digestRunning.value = true
  digestMessage.value = null
  digestError.value = null
  try {
    const result = await api.runDigest(stream.value.id)
    digestMessage.value = result.already_sent
      ? `今天已经发送过（${result.local_date}），未重复发送。`
      : `日报 ${result.status} · ${result.subject}`
    await load()
  } catch (caught) {
    digestError.value = caught instanceof Error ? caught.message : '日报发送失败'
  } finally {
    digestRunning.value = false
  }
}

async function saveRetention(): Promise<void> {
  retentionSaving.value = true
  retentionError.value = null
  retentionMessage.value = null
  try {
    retentionSettings.value = await api.saveRetentionSettings(retentionDraft.value)
    syncRetentionDraft(retentionSettings.value)
    retentionMessage.value = '回收策略已保存；下一次定时清理会使用新配置。'
    status.value = await api.opsStatus()
  } catch (caught) {
    retentionError.value = caught instanceof Error ? caught.message : '保存回收策略失败'
  } finally {
    retentionSaving.value = false
  }
}

onMounted(() => {
  void load()
})
</script>

<template>
  <section class="product-hero">
    <BackButton fallback="/" />
    <div class="product-title">
      <span class="product-symbol large">◎</span>
      <div>
        <p class="eyebrow">System · audit</p>
        <h1>系统运行状态</h1>
        <p class="muted">调度器、Agent Run、任务队列、通知与日报的健康度。</p>
      </div>
    </div>
    <button class="ghost-button" type="button" :disabled="loading" @click="load">
      {{ loading ? '刷新中…' : '刷新' }}
    </button>
  </section>

  <p v-if="error" class="error">{{ error }}</p>
  <p v-if="loading && !status" class="muted">加载系统状态…</p>

  <template v-if="status">
    <section v-if="!stream" class="panel empty-panel">
      <p class="eyebrow">No product</p>
      <h2>还没有 ACTIVE 投资产品</h2>
      <p class="muted">{{ status.message ?? '创建产品后，这里会显示调度与运行状态。' }}</p>
    </section>

    <template v-else>
      <section class="ops-grid">
        <article class="ops-card">
          <header>
            <span class="card-kicker">Scheduler</span>
            <span class="ops-status" :class="status.scheduler_enabled ? 'ok' : 'bad'">
              {{ status.scheduler_enabled ? 'ENABLED' : 'DISABLED' }}
            </span>
          </header>
          <h2>{{ stream.name }}</h2>
          <p class="muted">{{ stream.timezone }} · 每 {{ stream.monitor_interval_minutes }} 分钟</p>
          <div class="ops-row"><span>上次分析</span><strong>{{ fmt(stream.last_monitored_at) }}</strong></div>
          <div class="ops-row"><span>下次计划</span><strong>{{ fmt(stream.next_monitor_at) }}</strong></div>
        </article>

        <article class="ops-card">
          <header>
            <span class="card-kicker">Agent Runs · 24h</span>
            <span class="ops-status" :class="statusClass(status.runs.latest?.status)">
              {{ status.runs.latest?.status ?? '—' }}
            </span>
          </header>
          <h2>{{ counts(status.runs.last_24h) }}</h2>
          <p class="muted">7 天：{{ counts(status.runs.last_7d) }}</p>
          <div class="ops-row">
            <span>最近耗时</span>
            <strong>{{ status.runs.latest?.latency_ms ?? '—' }} ms</strong>
          </div>
          <p v-if="status.runs.last_failed" class="warning-inline">
            最近失败：{{ status.runs.last_failed.error_code }} ·
            {{ status.runs.last_failed.error_message }}
          </p>
        </article>

        <article class="ops-card">
          <header>
            <span class="card-kicker">Decisions</span>
            <span class="ops-status">{{ status.decisions.last_24h }} / 24h</span>
          </header>
          <h2>{{ status.decisions.latest?.decision ?? '—' }}</h2>
          <p class="muted">{{ status.decisions.latest?.priority ?? '还没有 Decision' }}</p>
          <div class="ops-row"><span>7 天总数</span><strong>{{ status.decisions.last_7d }}</strong></div>
          <p v-if="status.decisions.latest" class="ops-summary">
            {{ status.decisions.latest.summary.slice(0, 160) }}
          </p>
        </article>

        <article class="ops-card">
          <header>
            <span class="card-kicker">Jobs · queue</span>
            <span class="ops-status" :class="status.jobs.failed_24h > 0 ? 'warn' : 'ok'">
              {{ status.jobs.pending_or_running }} active
            </span>
          </header>
          <h2>{{ status.jobs.failed_24h }} failed / 24h</h2>
          <p class="muted">{{ counts(status.jobs.last_24h) }}</p>
          <div class="ops-row"><span>待处理 + 运行中</span><strong>{{ status.jobs.pending_or_running }}</strong></div>
        </article>

        <article class="ops-card">
          <header>
            <span class="card-kicker">Maintenance</span>
            <span class="ops-status" :class="retention?.enabled ? 'ok' : 'bad'">
              {{ retention?.enabled ? 'DAILY' : 'OFF' }}
            </span>
          </header>
          <h2>{{ retention?.last?.status ?? '未运行' }}</h2>
          <p class="muted">每天 03:15 UTC 清理过期市场数据</p>
          <div class="ops-row">
            <span>最近执行</span>
            <strong>{{ fmt(retention?.last?.finished_at) }}</strong>
          </div>
          <div class="ops-row">
            <span>删除</span>
            <strong>{{ counts(retention?.last?.deleted) }}</strong>
          </div>
          <p v-if="retention?.last?.last_error" class="warning-inline">
            {{ retention.last.last_error }}
          </p>
        </article>

        <article class="ops-card">
          <header>
            <span class="card-kicker">Market snapshot</span>
            <span class="ops-status" :class="statusClass(status.market.staleness)">
              {{ status.market.staleness }}
            </span>
          </header>
          <h2>{{ status.market.price ?? '—' }}</h2>
          <p class="muted">最近快照 {{ fmt(status.market.last_snapshot_at) }}</p>
          <div class="ops-row"><span>通知（7 天）</span><strong>{{ counts(status.notifications.last_7d) }}</strong></div>
        </article>

        <article class="ops-card">
          <header>
            <span class="card-kicker">Config</span>
            <span class="ops-status">read-only</span>
          </header>
          <h2>
            {{ status.config.llm_configured && status.config.email_configured ? '已配置' : '待配置' }}
          </h2>
          <div class="ops-row">
            <span>LLM</span>
            <strong :class="status.config.llm_configured ? 'ok-text' : 'bad-text'">
              {{ status.config.llm_configured ? 'OK' : '未配置' }}
            </strong>
          </div>
          <div class="ops-row">
            <span>SMTP</span>
            <strong :class="status.config.email_configured ? 'ok-text' : 'bad-text'">
              {{ status.config.email_configured ? 'OK' : '未配置' }}
            </strong>
          </div>
          <RouterLink class="inline-link" to="/settings">打开 Settings</RouterLink>
        </article>
      </section>

      <section class="panel">
        <div class="market-head">
          <div>
            <p class="eyebrow">Daily digest</p>
            <h2>每日 08:00 日报</h2>
          </div>
          <div class="digest-actions">
            <span class="ops-status" :class="digest?.enabled ? 'ok' : 'warn'">
              {{ digest?.enabled ? `开启 · ${digest.time}` : '未开启' }}
            </span>
            <button
              class="primary-button small"
              type="button"
              :disabled="digestRunning || !status.config.email_configured"
              :title="
                status.config.email_configured
                  ? '立即生成并发送今天的日报'
                  : '请先在 Settings 配置 SMTP'
              "
              @click="runDigest"
            >
              {{ digestRunning ? '生成并发送中…' : '立即发送日报' }}
            </button>
          </div>
        </div>
        <p v-if="!digest?.enabled" class="muted">
          日报未开启。去 Settings → 通知偏好打开「每日日报」。
        </p>
        <p v-if="!status.config.email_configured" class="error-hint">
          尚未配置 SMTP。请先到 Settings → 邮件通知保存并测试，再手动发送日报。
        </p>
        <p v-if="digestMessage" class="notice">{{ digestMessage }}</p>
        <p v-if="digestError" class="error">{{ digestError }}</p>
        <template v-if="digest">
          <div class="ops-row">
            <span>新闻</span>
            <strong>{{ digest.news_enabled ? '包含标题/链接' : '关闭' }}</strong>
          </div>
          <div v-if="digest.last" class="ops-row">
            <span>最近一次</span>
            <strong>
              {{ digest.last.local_date }} ·
              <span :class="statusClass(digest.last.status)">{{ digest.last.status }}</span>
              · {{ fmt(digest.last.sent_at) }}
            </strong>
          </div>
          <p v-else class="muted">还没有发送记录。</p>
          <p v-if="digest.last?.error" class="warning-inline">{{ digest.last.error }}</p>
        </template>
      </section>

      <section class="form-card settings-card">
        <div class="market-head">
          <div>
            <p class="eyebrow">Retention policy</p>
            <h2>市场数据保留策略</h2>
            <p class="muted">
              控制 K 线与行情快照的保留时间；过期数据由每日维护任务清理。
            </p>
          </div>
          <span class="ops-status" :class="retentionDraft.enabled ? 'ok' : 'bad'">
            {{ retentionDraft.enabled ? 'ENABLED' : 'DISABLED' }}
          </span>
        </div>

        <div class="form-grid">
          <label class="form-field checkbox">
            <input v-model="retentionDraft.enabled" type="checkbox" />
            <span>启用每日市场数据清理</span>
          </label>

          <label class="form-field">
            <span>1h K 线保留天数</span>
            <input v-model.number="retentionDraft.candle_1h_days" type="number" min="1" max="3650" />
          </label>

          <label class="form-field">
            <span>4h K 线保留天数</span>
            <input v-model.number="retentionDraft.candle_4h_days" type="number" min="1" max="3650" />
          </label>

          <label class="form-field">
            <span>1d K 线保留天数</span>
            <input v-model.number="retentionDraft.candle_1d_days" type="number" min="1" max="7300" />
          </label>

          <label class="form-field">
            <span>行情快照保留天数</span>
            <input v-model.number="retentionDraft.snapshot_days" type="number" min="1" max="3650" />
          </label>
        </div>

        <p class="muted">
          必须满足 1h ≤ 4h ≤ 1d；默认值来自环境变量，保存后以数据库设置为准。
          <span v-if="retentionSettings">
            当前来源：{{ retentionSettings.source === 'database' ? '数据库' : '环境变量默认值' }}
          </span>
        </p>

        <div class="form-actions">
          <button class="primary-button" type="button" :disabled="retentionSaving" @click="saveRetention">
            {{ retentionSaving ? '保存中…' : '保存回收策略' }}
          </button>
        </div>

        <p v-if="retentionError" class="error">{{ retentionError }}</p>
        <p v-if="retentionMessage" class="notice">{{ retentionMessage }}</p>
      </section>

      <section class="panel">
        <div class="market-head">
          <div>
            <p class="eyebrow">Recent runs</p>
            <h2>最近 Agent Run</h2>
          </div>
        </div>
        <table class="ops-table">
          <thead>
            <tr><th>时间</th><th>任务</th><th>状态</th><th>耗时</th><th>错误</th></tr>
          </thead>
          <tbody>
            <tr v-for="run in status.recent_runs" :key="run.id">
              <td class="mono">{{ fmt(run.started_at) }}</td>
              <td>{{ run.task_type }}</td>
              <td><span :class="statusClass(run.status)">{{ run.status }}</span></td>
              <td class="mono">{{ run.latency_ms ?? '—' }} ms</td>
              <td>{{ run.error_code ?? '—' }}</td>
            </tr>
          </tbody>
        </table>
      </section>

      <section class="panel">
        <div class="market-head">
          <div>
            <p class="eyebrow">Recent jobs</p>
            <h2>最近任务队列</h2>
          </div>
        </div>
        <table class="ops-table">
          <thead>
            <tr><th>计划</th><th>类型</th><th>状态</th><th>尝试</th><th>最后错误</th></tr>
          </thead>
          <tbody>
            <tr v-for="job in status.jobs.recent" :key="job.id">
              <td class="mono">{{ fmt(job.scheduled_at) }}</td>
              <td>{{ job.kind }}</td>
              <td><span :class="statusClass(job.status)">{{ job.status }}</span></td>
              <td class="mono">{{ job.attempts }}</td>
              <td>{{ job.last_error ?? '—' }}</td>
            </tr>
          </tbody>
        </table>
      </section>
    </template>
  </template>
</template>