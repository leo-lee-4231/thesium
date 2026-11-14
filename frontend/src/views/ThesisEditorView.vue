<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'

import {
  api,
  type Asset,
  type Stream,
  type ThesisDiffItem,
  type ThesisParseResult,
  type ThesisPolishResult,
  type ThesisVersion,
} from '@/api/client'

const route = useRoute()
const assets = ref<Asset[]>([])
const streams = ref<Stream[]>([])
const active = ref<ThesisVersion | null>(null)
const versions = ref<ThesisVersion[]>([])
const originalText = ref('')
const finalText = ref('')
const structuredText = ref('{}')
const polishResult = ref<ThesisPolishResult | null>(null)
const parseResult = ref<ThesisParseResult | null>(null)
const diff = ref<ThesisDiffItem[]>([])
const loading = ref(true)
const saving = ref(false)
const polishing = ref(false)
const parsing = ref(false)
const error = ref<string | null>(null)
const notice = ref<string | null>(null)

const symbol = computed(() => String(route.params.symbol ?? '').toUpperCase())
const asset = computed(() => assets.value.find((item) => item.symbol === symbol.value))
const stream = computed(() => streams.value.find((item) => item.asset_symbol === symbol.value))
const pending = computed(
  () => versions.value.find((version) => version.status === 'PENDING_CONFIRMATION') ?? null,
)
const currentVersion = computed(() => pending.value ?? active.value)
const llmMissing = computed(() => (error.value ?? '').includes('LLM_NOT_CONFIGURED'))

function applyVersion(version: ThesisVersion | null): void {
  if (!version) return
  originalText.value = version.original_text
  finalText.value = version.final_text ?? version.original_text
  structuredText.value = JSON.stringify(version.structured_content ?? {}, null, 2)
  diff.value = version.diff_from_previous ?? []
}

function fmtDate(value: string): string {
  return new Date(value).toLocaleString('zh-CN', {
    timeZone: 'Asia/Shanghai',
    hour12: false,
  })
}

async function load(): Promise<void> {
  loading.value = true
  error.value = null
  const [assetsResult, streamsResult] = await Promise.allSettled([api.assets(), api.streams()])
  if (assetsResult.status === 'fulfilled') assets.value = assetsResult.value
  if (streamsResult.status === 'fulfilled') streams.value = streamsResult.value
  if (!stream.value) {
    loading.value = false
    return
  }
  try {
    const [activeResult, versionsResult] = await Promise.all([
      api.thesis(stream.value.id),
      api.thesisVersions(stream.value.id),
    ])
    active.value = activeResult
    versions.value = versionsResult
    applyVersion(activeResult ?? versionsResult[0] ?? null)
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : 'Thesis 加载失败'
  } finally {
    loading.value = false
  }
}

async function refresh(): Promise<void> {
  if (!stream.value) return
  const [activeResult, versionsResult] = await Promise.all([
    api.thesis(stream.value.id),
    api.thesisVersions(stream.value.id),
  ])
  active.value = activeResult
  versions.value = versionsResult
}

async function runPolish(): Promise<void> {
  if (!stream.value) return
  polishing.value = true
  error.value = null
  polishResult.value = null
  try {
    polishResult.value = await api.polishThesis(stream.value.id, finalText.value || originalText.value)
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : 'AI 润色失败'
  } finally {
    polishing.value = false
  }
}

function adoptPolish(): void {
  if (!polishResult.value) return
  finalText.value = polishResult.value.polished_text
  polishResult.value = null
  notice.value = '已采用润色文本；你可以继续编辑后保存。'
}

async function runParse(): Promise<void> {
  if (!stream.value) return
  parsing.value = true
  error.value = null
  parseResult.value = null
  try {
    const result = await api.parseThesis(stream.value.id, finalText.value || originalText.value)
    parseResult.value = result
    structuredText.value = JSON.stringify(result.draft ?? {}, null, 2)
    notice.value = 'AI 已生成结构化草案；请检查字段后保存。'
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : 'AI 整理失败'
  } finally {
    parsing.value = false
  }
}

async function save(): Promise<void> {
  if (!stream.value) return
  saving.value = true
  error.value = null
  notice.value = null
  let structured: Record<string, unknown>
  try {
    structured = structuredText.value.trim() ? JSON.parse(structuredText.value) : {}
  } catch {
    error.value = '结构化内容不是合法 JSON'
    saving.value = false
    return
  }
  try {
    const result = await api.createThesis(stream.value.id, {
      original_text: originalText.value,
      final_text: finalText.value,
      structured_content: structured,
      source: 'USER',
      base_version_id: active.value?.id,
    })
    diff.value = result.version.diff_from_previous ?? []
    applyVersion(result.version)
    await refresh()
    notice.value = result.requires_confirmation
      ? '已保存为待确认版本；请检查 diff 后点击「确认生效」。'
      : '已保存并生效。'
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : '保存失败'
  } finally {
    saving.value = false
  }
}

async function confirm(): Promise<void> {
  if (!pending.value) return
  saving.value = true
  error.value = null
  try {
    await api.confirmThesis(pending.value.id)
    await refresh()
    applyVersion(active.value)
    notice.value = '已确认生效；旧版本已归档为 SUPERSEDED。'
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : '确认失败'
  } finally {
    saving.value = false
  }
}

async function reject(): Promise<void> {
  if (!pending.value) return
  saving.value = true
  error.value = null
  try {
    await api.rejectThesis(pending.value.id, '用户在编辑器拒绝')
    await refresh()
    applyVersion(active.value)
    notice.value = '已拒绝待确认版本。'
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : '拒绝失败'
  } finally {
    saving.value = false
  }
}

function loadVersion(version: ThesisVersion): void {
  applyVersion(version)
  notice.value = `已载入 v${version.version}（${version.status}）`
}

onMounted(() => {
  void load()
})
</script>

<template>
  <section class="product-hero">
    <RouterLink class="back-link" :to="`/products/${symbol.toLowerCase()}`">← 返回产品</RouterLink>
    <div class="product-title">
      <span class="product-symbol large">{{ asset?.symbol ?? '—' }}</span>
      <div>
        <p class="eyebrow">Investment Thesis</p>
        <h1>{{ asset?.name ?? symbol }} 的投资论点</h1>
        <p class="muted">原话保留、结构化整理、分级确认；一切变更都有版本。</p>
      </div>
    </div>
    <span v-if="currentVersion" class="status-pill" :class="{ active: currentVersion.status === 'ACTIVE' }">
      v{{ currentVersion.version }} · {{ currentVersion.status }}
    </span>
  </section>

  <div v-if="!loading && !stream" class="banner">
    <strong>还没有投资产品</strong>
    <span>
      先创建产品，再写投资论点。
      <RouterLink :to="`/products/new?symbol=${symbol}`">创建投资产品</RouterLink>
    </span>
  </div>

  <p v-if="loading" class="muted">加载 Thesis…</p>
  <p v-if="error" class="error">
    {{ error }}
    <RouterLink v-if="llmMissing" class="inline-link" to="/settings">去 Settings 配置 LLM</RouterLink>
  </p>
  <p v-if="notice" class="notice">{{ notice }}</p>

  <template v-if="stream && !loading">
    <div class="thesis-grid">
      <section class="thesis-column">
        <div class="thesis-head">
          <div>
            <p class="eyebrow">Your words</p>
            <h2>原话与确认正文</h2>
          </div>
          <button class="ghost-button" type="button" :disabled="polishing" @click="runPolish">
            {{ polishing ? '润色中…' : 'AI 润色' }}
          </button>
        </div>

        <label class="form-field">
          <span>原文（你的原始输入，不覆盖）</span>
          <textarea v-model="originalText" rows="7" />
        </label>
        <label class="form-field">
          <span>确认正文（可编辑，Agent 读取这一份）</span>
          <textarea v-model="finalText" rows="7" />
        </label>
        <button class="ghost-button left" type="button" @click="finalText = originalText">
          用原文同步确认正文
        </button>

        <div v-if="polishResult" class="ai-result">
          <header>
            <strong>AI 润色建议</strong>
            <button class="primary-button small" type="button" @click="adoptPolish">采用润色</button>
          </header>
          <p class="ai-text">{{ polishResult.polished_text }}</p>
          <p v-if="!polishResult.meaning_preserved" class="error">模型认为语义可能未完全保持，请仔细核对。</p>
          <ul v-if="polishResult.warnings.length" class="warning-list">
            <li v-for="warning in polishResult.warnings" :key="warning">{{ warning }}</li>
          </ul>
        </div>
      </section>

      <section class="thesis-column">
        <div class="thesis-head">
          <div>
            <p class="eyebrow">Structured view</p>
            <h2>结构化字段</h2>
          </div>
          <button class="ghost-button" type="button" :disabled="parsing" @click="runParse">
            {{ parsing ? '整理中…' : 'AI 帮我整理' }}
          </button>
        </div>

        <label class="form-field">
          <span>JSON（可手改；AI 整理会回填）</span>
          <textarea v-model="structuredText" rows="18" spellcheck="false" />
        </label>

        <div v-if="parseResult" class="ai-result">
          <strong>整理结果</strong>
          <p class="muted">
            AI 发现的缺失或歧义会列在下面。它们只是建议，不阻塞保存，也不会自动改你的原文或 JSON；
            补充原文后重新整理，或直接在 JSON 里修正即可。
          </p>
          <p v-if="parseResult.clarifying_questions.length" class="muted">
            建议澄清（{{ parseResult.clarifying_questions.length }} 条，最多 5 条）：
          </p>
          <ul class="warning-list">
            <li v-for="question in parseResult.clarifying_questions" :key="question">{{ question }}</li>
          </ul>
          <ul v-if="parseResult.unparsed.length" class="warning-list">
            <li v-for="item in parseResult.unparsed" :key="item.text">未整理：{{ item.text }}（{{ item.reason }}）</li>
          </ul>
        </div>
      </section>
    </div>

    <div class="thesis-actions">
      <button class="primary-button" type="button" :disabled="saving" @click="save">
        {{ saving ? '保存中…' : '保存（MATERIAL 需确认）' }}
      </button>
      <button v-if="pending" class="primary-button warn" type="button" :disabled="saving" @click="confirm">
        确认生效（v{{ pending.version }}）
      </button>
      <button v-if="pending" class="ghost-button" type="button" :disabled="saving" @click="reject">
        拒绝待确认版本
      </button>
      <span v-if="active" class="muted">当前生效：v{{ active.version }}</span>
    </div>

    <section v-if="diff.length" class="diff-panel">
      <div class="thesis-head">
        <div>
          <p class="eyebrow">Change receipt</p>
          <h2>变更 diff</h2>
        </div>
        <span class="mono">{{ diff.length }} 项</span>
      </div>
      <ul class="diff-list">
        <li v-for="item in diff" :key="`${item.path}-${item.op}`">
          <span class="diff-class" :class="item.classification.toLowerCase()">{{ item.classification }}</span>
          <span class="mono">{{ item.op }} {{ item.path }}</span>
          <span class="muted">{{ JSON.stringify(item.after) }}</span>
        </li>
      </ul>
    </section>

    <section class="history-panel">
      <div class="thesis-head">
        <div>
          <p class="eyebrow">History</p>
          <h2>版本历史</h2>
        </div>
        <span class="mono">{{ versions.length }} 个版本</span>
      </div>
      <ul class="history-list">
        <li v-for="version in versions" :key="version.id">
          <span class="version-badge">v{{ version.version }}</span>
          <span class="status-pill" :class="{ active: version.status === 'ACTIVE' }">{{ version.status }}</span>
          <span class="diff-class" :class="version.change_class.toLowerCase()">{{ version.change_class }}</span>
          <span class="muted">{{ version.final_text?.slice(0, 48) ?? '—' }}</span>
          <span class="mono">{{ fmtDate(version.created_at) }}</span>
          <button class="ghost-button small" type="button" @click="loadVersion(version)">载入</button>
        </li>
      </ul>
    </section>
  </template>
</template>