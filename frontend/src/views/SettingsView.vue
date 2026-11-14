<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { api, type LLMStatus } from '@/api/client'

const status = ref<LLMStatus | null>(null)
const baseUrl = ref('')
const model = ref('')
const apiKey = ref('')
const clearKey = ref(false)
const loading = ref(true)
const saving = ref(false)
const testing = ref(false)
const error = ref<string | null>(null)
const notice = ref<string | null>(null)
const testResult = ref<{ ok: boolean; latency_ms?: number; error?: string; message?: string } | null>(null)

const sourceLabel = computed(() => {
  if (!status.value) return '—'
  if (status.value.source === 'database') return '数据库'
  if (status.value.source === 'environment') return '环境变量（保存后会切到数据库）'
  return '未配置'
})

function fmtDate(value: string | null): string {
  if (!value) return '—'
  return new Date(value).toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai', hour12: false })
}

async function load(): Promise<void> {
  loading.value = true
  error.value = null
  try {
    const result = await api.llmStatus()
    status.value = result
    baseUrl.value = result.base_url
    model.value = result.model
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : '配置加载失败'
  } finally {
    loading.value = false
  }
}

async function save(): Promise<void> {
  saving.value = true
  error.value = null
  notice.value = null
  try {
    const result = await api.saveLlmConfig({
      base_url: baseUrl.value,
      model: model.value,
      api_key: apiKey.value || undefined,
      clear_api_key: clearKey.value,
    })
    status.value = result
    apiKey.value = ''
    clearKey.value = false
    notice.value = '已保存到数据库。API Key 已加密存储，不会回显。'
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : '保存失败'
  } finally {
    saving.value = false
  }
}

async function test(): Promise<void> {
  testing.value = true
  error.value = null
  testResult.value = null
  try {
    testResult.value = await api.testLlm({
      base_url: baseUrl.value,
      model: model.value,
      api_key: apiKey.value || undefined,
    })
    await load()
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : '连接测试失败'
  } finally {
    testing.value = false
  }
}

onMounted(() => {
  void load()
})
</script>

<template>
  <section class="product-hero">
    <RouterLink class="back-link" to="/">← 返回产品列表</RouterLink>
    <div class="product-title">
      <span class="product-symbol large">⚙</span>
      <div>
        <p class="eyebrow">Settings</p>
        <h1>LLM Provider</h1>
        <p class="muted">OpenAI 兼容接口；Key 加密保存，前端不会回显。</p>
      </div>
    </div>
    <span class="status-pill" :class="{ active: status?.configured }">
      {{ status?.configured ? '已配置' : '未配置' }}
    </span>
  </section>

  <p v-if="loading" class="muted">加载配置…</p>
  <p v-if="error" class="error">{{ error }}</p>
  <p v-if="notice" class="notice">{{ notice }}</p>

  <section v-if="status" class="form-card">
    <div class="settings-status">
      <div>
        <span>来源</span>
        <strong>{{ sourceLabel }}</strong>
      </div>
      <div>
        <span>状态</span>
        <strong>{{ status.status }}</strong>
      </div>
      <div>
        <span>Key</span>
        <strong>{{ status.has_api_key ? `已保存 · …${status.api_key_hint ?? ''}` : '未保存' }}</strong>
      </div>
      <div>
        <span>最近测试</span>
        <strong>{{ fmtDate(status.last_tested_at) }}</strong>
      </div>
    </div>

    <div class="form-grid">
      <label class="form-field">
        <span>Base URL</span>
        <input v-model="baseUrl" type="text" placeholder="https://api.deepseek.com/v1" />
        <small>必须包含 OpenAI 兼容路径，通常以 /v1 结尾。</small>
      </label>

      <label class="form-field">
        <span>Model</span>
        <input v-model="model" type="text" placeholder="deepseek-chat" />
      </label>

      <label class="form-field">
        <span>API Key</span>
        <input v-model="apiKey" type="password" autocomplete="new-password" placeholder="留空表示不修改" />
        <small>只写入，不回显；保存后仅显示末 4 位。</small>
      </label>

      <label class="form-field checkbox">
        <input v-model="clearKey" type="checkbox" />
        <span>清除已保存的 API Key</span>
      </label>
    </div>

    <div class="form-actions">
      <button class="ghost-button" type="button" :disabled="testing || saving" @click="test">
        {{ testing ? '测试中…' : '测试连接' }}
      </button>
      <button class="primary-button" type="button" :disabled="saving || testing" @click="save">
        {{ saving ? '保存中…' : '保存到数据库' }}
      </button>
    </div>

    <p v-if="testResult" class="test-result" :class="{ ok: testResult.ok }">
      <template v-if="testResult.ok">连接成功 · {{ testResult.latency_ms }} ms</template>
      <template v-else>连接失败 · {{ testResult.error }} · {{ testResult.message }}</template>
    </p>

    <p class="form-note">
      Thesis 的「AI 润色」「AI 帮我整理」会使用这里保存的配置。修改后无需重启 API；保存即生效。
    </p>
  </section>
</template>