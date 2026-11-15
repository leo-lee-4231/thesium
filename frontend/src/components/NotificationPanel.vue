<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'

import { api, type NotificationItem } from '@/api/client'

const props = defineProps<{ streamId: string }>()

const notifications = ref<NotificationItem[]>([])
const loading = ref(true)
const error = ref<string | null>(null)
const retrying = ref<string | null>(null)

function fmtDate(value: string): string {
  return new Date(value).toLocaleString('zh-CN', {
    timeZone: 'Asia/Shanghai',
    hour12: false,
  })
}

function statusLabel(item: NotificationItem): string {
  if (item.status === 'SENT') return '已发送'
  if (item.status === 'PENDING') return '待发送'
  if (item.status === 'RETRYING') return '重试中'
  if (item.status === 'FAILED') return '发送失败'
  return '已跳过'
}

function deliveryLabel(channel: string): string {
  return channel === 'EMAIL' ? '邮件' : channel === 'FEISHU' ? '飞书' : 'Web'
}

function canRetry(item: NotificationItem): boolean {
  return item.deliveries.some(
    (delivery) =>
      delivery.channel === 'EMAIL' &&
      (delivery.status === 'FAILED' || delivery.status === 'SKIPPED'),
  )
}

async function load(): Promise<void> {
  loading.value = true
  error.value = null
  try {
    notifications.value = await api.notifications(props.streamId, 12)
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : '通知记录加载失败'
  } finally {
    loading.value = false
  }
}

async function retry(item: NotificationItem): Promise<void> {
  retrying.value = item.id
  error.value = null
  try {
    await api.retryNotification(item.id)
    await load()
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : '重试失败'
  } finally {
    retrying.value = null
  }
}

function onChanged(): void {
  void load()
}

onMounted(() => {
  void load()
  window.addEventListener('thesium:notifications-changed', onChanged)
})

onUnmounted(() => {
  window.removeEventListener('thesium:notifications-changed', onChanged)
})
</script>

<template>
  <section class="notification-panel">
    <div class="market-head">
      <div>
        <p class="eyebrow">Notifications</p>
        <h2>通知记录</h2>
      </div>
      <button class="ghost-button small" type="button" :disabled="loading" @click="load">
        刷新
      </button>
    </div>

    <p class="muted decision-hint">
      程序按规则裁决是否打扰：普通 WAIT / HOLD 不发，重要变化才发；被跳过也会保留原因。
    </p>

    <p v-if="error" class="error">{{ error }}</p>
    <p v-if="loading" class="muted">加载通知…</p>
    <p v-else-if="notifications.length === 0" class="muted">
      还没有通知记录。重要变化、论点冲突或风险突破时会出现在这里。
    </p>

    <ul v-else class="notification-list">
      <li v-for="item in notifications" :key="item.id" class="notification-card">
        <header>
          <span class="decision-badge small" :class="item.decision.toLowerCase()">
            {{ item.decision }}
          </span>
          <span class="priority-chip">{{ item.priority }}</span>
          <span class="notification-status" :class="item.status.toLowerCase()">
            {{ statusLabel(item) }}
          </span>
          <span class="mono notification-time">{{ fmtDate(item.created_at) }}</span>
        </header>
        <strong class="notification-title">{{ item.title }}</strong>
        <p class="notification-reason">{{ item.reason }}</p>
        <div class="notification-deliveries">
          <span
            v-for="delivery in item.deliveries"
            :key="delivery.channel"
            class="delivery-chip"
            :class="delivery.status.toLowerCase()"
            :title="delivery.last_error ?? ''"
          >
            {{ deliveryLabel(delivery.channel) }} · {{ delivery.status }}
            <template v-if="delivery.attempts > 1"> · {{ delivery.attempts }} 次</template>
          </span>
          <span v-if="item.triggered_rules.length" class="mono">
            规则 {{ item.triggered_rules.join(', ') }}
          </span>
        </div>
        <p
          v-if="
            item.deliveries.some(
              (d) => d.channel === 'EMAIL' && d.last_error === 'SMTP_NOT_CONFIGURED',
            )
          "
          class="warning-inline"
        >
          邮件未配置，本次只记录到 Web。
          <RouterLink class="inline-link" to="/settings">去 Settings 配置 SMTP</RouterLink>
        </p>
        <p
          v-else-if="item.deliveries.some((d) => d.last_error)"
          class="warning-inline"
        >
          {{ item.deliveries.find((d) => d.last_error)?.last_error }}
        </p>
        <div class="notification-actions">
          <details>
            <summary>查看摘要正文</summary>
            <pre class="notification-body">{{ item.body_text }}</pre>
          </details>
          <button
            v-if="canRetry(item)"
            class="ghost-button small"
            type="button"
            :disabled="retrying === item.id"
            @click="retry(item)"
          >
            {{ retrying === item.id ? '重试中…' : '重试邮件' }}
          </button>
        </div>
      </li>
    </ul>
  </section>
</template>