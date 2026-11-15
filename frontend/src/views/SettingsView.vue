<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import BackButton from '@/components/BackButton.vue'
import {
  api,
  type EmailStatus,
  type LLMStatus,
  type NetworkStatus,
  type NotificationPreferences,
  type OkxCheckResult,
} from '@/api/client'

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

const email = ref<EmailStatus | null>(null)
const emailHost = ref('')
const emailPort = ref(587)
const emailUsername = ref('')
const emailPassword = ref('')
const emailClearPassword = ref(false)
const emailFrom = ref('')
const emailTo = ref('')
const emailFromName = ref('Thesium')
const emailTls = ref(true)
const emailSsl = ref(false)
const emailSaving = ref(false)
const emailTesting = ref(false)
const emailError = ref<string | null>(null)
const emailNotice = ref<string | null>(null)
const emailTest = ref<{ ok: boolean; latency_ms?: number; error?: string; message?: string } | null>(null)

const network = ref<NetworkStatus | null>(null)
const networkEnabled = ref(false)
const networkUrl = ref('')
const networkSaving = ref(false)
const networkError = ref<string | null>(null)
const networkNotice = ref<string | null>(null)
const probeLoading = ref(false)
const probeResult = ref<OkxCheckResult | null>(null)

const prefs = ref<NotificationPreferences | null>(null)
const prefsSaving = ref(false)
const prefsError = ref<string | null>(null)
const prefsNotice = ref<string | null>(null)

const networkSourceLabel = computed(() => {
  if (!network.value) return '—'
  if (network.value.source === 'database') return '数据库'
  if (network.value.source === 'environment') return '环境变量回退'
  return '未配置（默认不走代理）'
})

const llmSourceLabel = computed(() => {
  if (!status.value) return '—'
  if (status.value.source === 'database') return '数据库'
  if (status.value.source === 'environment') return '环境变量（保存后会切到数据库）'
  return '未配置'
})

function fmtDate(value: string | null): string {
  if (!value) return '—'
  return new Date(value).toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai', hour12: false })
}

async function loadLlm(): Promise<void> {
  try {
    const result = await api.llmStatus()
    status.value = result
    baseUrl.value = result.base_url
    model.value = result.model
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : '配置加载失败'
  }
}

async function loadEmail(): Promise<void> {
  try {
    const result = await api.emailStatus()
    email.value = result
    emailHost.value = result.host
    emailPort.value = result.port
    emailUsername.value = result.username
    emailFrom.value = result.from_address
    emailTo.value = result.to_address
    emailFromName.value = result.from_name || 'Thesium'
    emailTls.value = result.use_tls
    emailSsl.value = result.use_ssl
  } catch (caught) {
    emailError.value = caught instanceof Error ? caught.message : '邮件配置加载失败'
  }
}

async function loadNetwork(): Promise<void> {
  try {
    const result = await api.networkStatus()
    network.value = result
    networkEnabled.value = result.market_proxy_enabled
    networkUrl.value = result.market_proxy_url
  } catch (caught) {
    networkError.value = caught instanceof Error ? caught.message : '网络设置加载失败'
  }
}

async function loadPrefs(): Promise<void> {
  try {
    prefs.value = await api.notificationPreferences()
  } catch (caught) {
    prefsError.value = caught instanceof Error ? caught.message : '通知偏好加载失败'
  }
}

async function load(): Promise<void> {
  loading.value = true
  error.value = null
  await Promise.all([loadLlm(), loadEmail(), loadNetwork(), loadPrefs()])
  loading.value = false
}

async function saveLlm(): Promise<void> {
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

async function testLlm(): Promise<void> {
  testing.value = true
  error.value = null
  testResult.value = null
  try {
    testResult.value = await api.testLlm({
      base_url: baseUrl.value,
      model: model.value,
      api_key: apiKey.value || undefined,
    })
    await loadLlm()
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : '连接测试失败'
  } finally {
    testing.value = false
  }
}

function onTlsChange(): void {
  if (emailTls.value) emailSsl.value = false
}

function onSslChange(): void {
  if (emailSsl.value) emailTls.value = false
}

async function saveEmail(): Promise<void> {
  emailSaving.value = true
  emailError.value = null
  emailNotice.value = null
  emailTest.value = null
  try {
    const result = await api.saveEmailConfig({
      host: emailHost.value,
      port: Number(emailPort.value),
      from_address: emailFrom.value,
      to_address: emailTo.value || undefined,
      from_name: emailFromName.value || undefined,
      username: emailUsername.value || undefined,
      password: emailPassword.value || undefined,
      clear_password: emailClearPassword.value,
      use_tls: emailTls.value,
      use_ssl: emailSsl.value,
    })
    email.value = result
    emailPassword.value = ''
    emailClearPassword.value = false
    emailNotice.value = 'SMTP 配置已保存。密码加密存储，不会回显。'
  } catch (caught) {
    emailError.value = caught instanceof Error ? caught.message : '保存失败'
  } finally {
    emailSaving.value = false
  }
}

async function testEmail(): Promise<void> {
  emailTesting.value = true
  emailError.value = null
  emailTest.value = null
  try {
    emailTest.value = await api.testEmail({
      host: emailHost.value,
      port: Number(emailPort.value),
      from_address: emailFrom.value,
      to_address: emailTo.value || undefined,
      from_name: emailFromName.value || undefined,
      username: emailUsername.value || undefined,
      password: emailPassword.value || undefined,
      use_tls: emailTls.value,
      use_ssl: emailSsl.value,
    })
    if (emailTest.value.ok) {
      emailTest.value = { ...emailTest.value, message: '测试邮件已发送，请查收。' }
    }
  } catch (caught) {
    emailError.value = caught instanceof Error ? caught.message : '测试邮件发送失败'
  } finally {
    emailTesting.value = false
  }
}

async function saveNetwork(): Promise<void> {
  networkSaving.value = true
  networkError.value = null
  networkNotice.value = null
  probeResult.value = null
  try {
    network.value = await api.saveNetworkSettings({
      market_proxy_enabled: networkEnabled.value,
      market_proxy_url: networkUrl.value || undefined,
    })
    networkEnabled.value = network.value.market_proxy_enabled
    networkUrl.value = network.value.market_proxy_url
    networkNotice.value = '网络设置已保存；API 与 Worker 会按新设置取行情，无需重启。'
  } catch (caught) {
    networkError.value = caught instanceof Error ? caught.message : '保存失败'
  } finally {
    networkSaving.value = false
  }
}

async function testMarket(): Promise<void> {
  probeLoading.value = true
  networkError.value = null
  probeResult.value = null
  try {
    probeResult.value = await api.okxCheck('BTC-USDT')
  } catch (caught) {
    networkError.value = caught instanceof Error ? caught.message : '行情连接测试失败'
  } finally {
    probeLoading.value = false
  }
}

async function savePrefs(): Promise<void> {
  if (!prefs.value) return
  prefsSaving.value = true
  prefsError.value = null
  prefsNotice.value = null
  try {
    prefs.value = await api.saveNotificationPreferences(prefs.value)
    prefsNotice.value = '通知偏好已保存。'
  } catch (caught) {
    prefsError.value = caught instanceof Error ? caught.message : '保存失败'
  } finally {
    prefsSaving.value = false
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
      <span class="product-symbol large">⚙</span>
      <div>
        <p class="eyebrow">Settings</p>
        <h1>模型、邮件与通知</h1>
        <p class="muted">全部保存到本地 PostgreSQL；密钥加密存储，前端不回显。</p>
      </div>
    </div>
  </section>

  <p v-if="loading" class="muted">加载配置…</p>
  <p v-if="error" class="error">{{ error }}</p>
  <p v-if="notice" class="notice">{{ notice }}</p>

  <section v-if="status" class="form-card settings-card">
    <header class="settings-card-head">
      <div>
        <p class="eyebrow">LLM Provider</p>
        <h2>模型</h2>
      </div>
      <span class="status-pill" :class="{ active: status.configured }">
        {{ status.configured ? '已配置' : '未配置' }}
      </span>
    </header>

    <div class="settings-status">
      <div>
        <span>来源</span>
        <strong>{{ llmSourceLabel }}</strong>
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
      <button class="ghost-button" type="button" :disabled="testing || saving" @click="testLlm">
        {{ testing ? '测试中…' : '测试连接' }}
      </button>
      <button class="primary-button" type="button" :disabled="saving || testing" @click="saveLlm">
        {{ saving ? '保存中…' : '保存到数据库' }}
      </button>
    </div>

    <p v-if="testResult" class="test-result" :class="{ ok: testResult.ok }">
      <template v-if="testResult.ok">连接成功 · {{ testResult.latency_ms }} ms</template>
      <template v-else>连接失败 · {{ testResult.error }} · {{ testResult.message }}</template>
    </p>

    <p class="form-note">
      Thesis 的「AI 润色」「AI 帮我整理」与只读对话都使用这里保存的配置。修改后无需重启 API。
    </p>
  </section>

  <section v-if="network" class="form-card settings-card">
    <header class="settings-card-head">
      <div>
        <p class="eyebrow">Network · OKX</p>
        <h2>行情代理</h2>
      </div>
      <span class="status-pill" :class="{ active: networkEnabled }">
        {{ networkEnabled ? '使用代理' : '直连' }}
      </span>
    </header>

    <div class="settings-status">
      <div>
        <span>配置来源</span>
        <strong>{{ networkSourceLabel }}</strong>
      </div>
      <div>
        <span>当前生效</span>
        <strong class="mono">{{ network.effective_proxy ?? '不使用代理' }}</strong>
      </div>
      <div>
        <span>环境变量回退</span>
        <strong class="mono">{{ network.env_fallback ?? '—' }}</strong>
      </div>
      <div>
        <span>默认 URL</span>
        <strong class="mono">{{ network.default_url }}</strong>
      </div>
    </div>

    <div class="form-grid">
      <label class="form-field checkbox">
        <input v-model="networkEnabled" type="checkbox" />
        <span>OKX 行情请求使用代理</span>
      </label>

      <label class="form-field">
        <span>代理 URL</span>
        <input
          v-model="networkUrl"
          type="text"
          :disabled="!networkEnabled"
          placeholder="socks5h://127.0.0.1:7897"
        />
        <small>
          支持 http://、https://、socks5://、socks5h://。建议用 socks5h，让 DNS 在代理侧解析。
        </small>
      </label>
    </div>

    <div class="form-actions">
      <button class="ghost-button" type="button" :disabled="probeLoading" @click="testMarket">
        {{ probeLoading ? '测试中…' : '测试行情连接' }}
      </button>
      <button class="primary-button" type="button" :disabled="networkSaving" @click="saveNetwork">
        {{ networkSaving ? '保存中…' : '保存网络设置' }}
      </button>
    </div>

    <p v-if="networkError" class="error">{{ networkError }}</p>
    <p v-if="networkNotice" class="notice">{{ networkNotice }}</p>
    <p v-if="probeResult" class="test-result" :class="{ ok: probeResult.ok }">
      <template v-if="probeResult.ok">
        连接成功 · {{ probeResult.price }} · {{ probeResult.staleness }} ·
        {{ probeResult.latency_ms }} ms · 来源 {{ probeResult.proxy_source }}
      </template>
      <template v-else>
        连接失败 · {{ probeResult.error_type }} · {{ probeResult.error }}
      </template>
    </p>

    <p class="form-note">
      关闭开关会完全绕过代理（包括环境变量），当前网络下 OKX 直连可能失败。
      保存后 API 与 Worker 在下一次请求/任务时生效，无需重启。测试使用已保存的设置。
    </p>
  </section>

  <section v-if="email" class="form-card settings-card">
    <header class="settings-card-head">
      <div>
        <p class="eyebrow">Email · SMTP</p>
        <h2>邮件通知</h2>
      </div>
      <span class="status-pill" :class="{ active: email.configured && email.verified_at }">
        {{ email.verified_at ? '已验证' : email.configured ? '待验证' : '未配置' }}
      </span>
    </header>

    <div class="settings-status">
      <div>
        <span>状态</span>
        <strong>{{ email.status }}</strong>
      </div>
      <div>
        <span>密码</span>
        <strong>{{ email.has_password ? '已保存（加密）' : '未保存' }}</strong>
      </div>
      <div>
        <span>最近测试</span>
        <strong>{{ fmtDate(email.last_tested_at) }}</strong>
      </div>
      <div>
        <span>验证时间</span>
        <strong>{{ fmtDate(email.verified_at) }}</strong>
      </div>
    </div>

    <div class="form-grid">
      <label class="form-field">
        <span>SMTP Host</span>
        <input v-model="emailHost" type="text" placeholder="smtp.example.com" />
      </label>
      <label class="form-field">
        <span>Port</span>
        <input v-model.number="emailPort" type="number" min="1" max="65535" />
        <small>STARTTLS 常用 587；SSL 常用 465。</small>
      </label>
      <label class="form-field">
        <span>Username</span>
        <input v-model="emailUsername" type="text" autocomplete="username" placeholder="登录用户名，可留空" />
      </label>
      <label class="form-field">
        <span>Password</span>
        <input v-model="emailPassword" type="password" autocomplete="new-password" placeholder="留空表示不修改" />
        <small>只写入，不回显；清除请勾选下方选项。</small>
      </label>
      <label class="form-field">
        <span>From address</span>
        <input v-model="emailFrom" type="email" placeholder="thesium@example.com" />
      </label>
      <label class="form-field">
        <span>To address</span>
        <input v-model="emailTo" type="email" placeholder="留空则发到 From 地址" />
        <small>决策摘要的收件地址；建议填你自己的邮箱。</small>
      </label>
      <label class="form-field">
        <span>From name</span>
        <input v-model="emailFromName" type="text" placeholder="Thesium" />
      </label>
      <label class="form-field checkbox">
        <input v-model="emailClearPassword" type="checkbox" />
        <span>清除已保存的 SMTP 密码</span>
      </label>
      <label class="form-field checkbox">
        <input v-model="emailTls" type="checkbox" @change="onTlsChange" />
        <span>使用 STARTTLS</span>
      </label>
      <label class="form-field checkbox">
        <input v-model="emailSsl" type="checkbox" @change="onSslChange" />
        <span>使用 SSL（通常 465）</span>
      </label>
    </div>

    <div class="form-actions">
      <button class="ghost-button" type="button" :disabled="emailTesting || emailSaving" @click="testEmail">
        {{ emailTesting ? '发送中…' : '发送测试邮件' }}
      </button>
      <button class="primary-button" type="button" :disabled="emailSaving || emailTesting" @click="saveEmail">
        {{ emailSaving ? '保存中…' : '保存 SMTP 配置' }}
      </button>
    </div>

    <p v-if="emailError" class="error">{{ emailError }}</p>
    <p v-if="emailNotice" class="notice">{{ emailNotice }}</p>
    <p v-if="emailTest" class="test-result" :class="{ ok: emailTest.ok }">
      <template v-if="emailTest.ok">
        发送成功 · {{ emailTest.latency_ms }} ms · {{ emailTest.message }}
      </template>
      <template v-else>发送失败 · {{ emailTest.error }} · {{ emailTest.message }}</template>
    </p>

    <p class="form-note">
      测试使用当前表单值，不会保存；保存后通知才会使用新配置。邮件只包含决策摘要与 Web 链接，
      不含 API Key 或完整 Prompt；失败会按 1/5/30 分钟重试，最多 3 次。
    </p>
  </section>

  <section v-if="prefs" class="form-card settings-card">
    <header class="settings-card-head">
      <div>
        <p class="eyebrow">Notification policy</p>
        <h2>通知偏好</h2>
      </div>
      <span class="status-pill active">程序裁决</span>
    </header>

    <div class="settings-status">
      <div>
        <span>决策通知</span>
        <strong>{{ prefs.decision_alert_enabled ? '开' : '关' }}</strong>
      </div>
      <div>
        <span>风险通知</span>
        <strong>{{ prefs.risk_alert_enabled ? '开' : '关' }}</strong>
      </div>
      <div>
        <span>邮件渠道</span>
        <strong>{{ prefs.email_enabled ? '开' : '关' }}</strong>
      </div>
      <div>
        <span>免打扰</span>
        <strong>{{ prefs.quiet_hours_enabled ? `${prefs.quiet_hours_start}–${prefs.quiet_hours_end}` : '关' }}</strong>
      </div>
    </div>

    <div class="form-grid">
      <label class="form-field checkbox">
        <input v-model="prefs.decision_alert_enabled" type="checkbox" />
        <span>重要决策通知（HIGH / URGENT、类别跃迁、论点冲突）</span>
      </label>
      <label class="form-field checkbox">
        <input v-model="prefs.risk_alert_enabled" type="checkbox" />
        <span>风险类通知（风险预算被突破）</span>
      </label>
      <label class="form-field checkbox">
        <input v-model="prefs.email_enabled" type="checkbox" />
        <span>通过邮件发送（关闭后仍保留 Web 通知中心记录）</span>
      </label>
      <label class="form-field checkbox">
        <input v-model="prefs.quiet_hours_enabled" type="checkbox" />
        <span>启用免打扰时段（URGENT 可绕过）</span>
      </label>
      <label class="form-field">
        <span>免打扰开始</span>
        <input v-model="prefs.quiet_hours_start" type="time" />
      </label>
      <label class="form-field">
        <span>免打扰结束</span>
        <input v-model="prefs.quiet_hours_end" type="time" />
      </label>
      <label class="form-field">
        <span>每日邮件上限</span>
        <input v-model.number="prefs.daily_email_limit" type="number" min="1" max="50" />
      </label>
      <label class="form-field">
        <span>相同通知冷却（分钟）</span>
        <input v-model.number="prefs.cooldown_minutes" type="number" min="0" max="10080" />
      </label>
    </div>

    <div class="form-actions">
      <button class="primary-button" type="button" :disabled="prefsSaving" @click="savePrefs">
        {{ prefsSaving ? '保存中…' : '保存通知偏好' }}
      </button>
    </div>

    <p v-if="prefsError" class="error">{{ prefsError }}</p>
    <p v-if="prefsNotice" class="notice">{{ prefsNotice }}</p>

    <p class="form-note">
      普通 WAIT / HOLD 不打扰；HOLD→SELL 等类别跃迁、HIGH/URGENT、论点转 CONFLICTING、
      风险预算突破才会进入通知。模型只建议，最终由程序规则裁决并记录原因。
    </p>
  </section>
</template>