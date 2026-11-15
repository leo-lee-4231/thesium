<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'

import {
  api,
  streamChat,
  type ChatDone,
  type ChatEvent,
  type ChatMessage,
  type Conversation,
  type Stream,
} from '@/api/client'

const route = useRoute()
const streams = ref<Stream[]>([])
const conversations = ref<Conversation[]>([])
const activeId = ref<string | null>(null)
const messages = ref<ChatMessage[]>([])
const input = ref('')
const loading = ref(true)
const sending = ref(false)
const error = ref<string | null>(null)
const statusText = ref('')
const streamingText = ref('')
const lastDone = ref<ChatDone | null>(null)
const scrollBox = ref<HTMLElement | null>(null)
let controller: AbortController | null = null

const symbol = computed(() => String(route.params.symbol ?? '').toUpperCase())
const stream = computed(() => streams.value.find((item) => item.asset_symbol === symbol.value))
const activeConversation = computed(
  () => conversations.value.find((item) => item.id === activeId.value) ?? null,
)

const quickPrompts = [
  '现在价格和关键指标怎么样？',
  '我的投资论点还成立吗？哪里不一致？',
  '如果价格再跌 5%，我的持仓风险如何？',
  '我有点焦虑，帮我按 if-then 理一下下一步。',
]

function fmtTime(value: string): string {
  return new Date(value).toLocaleString('zh-CN', {
    timeZone: 'Asia/Shanghai',
    hour12: false,
  })
}

async function scrollToBottom(): Promise<void> {
  await nextTick()
  if (scrollBox.value) scrollBox.value.scrollTop = scrollBox.value.scrollHeight
}

async function loadMessages(): Promise<void> {
  if (!activeId.value) return
  messages.value = await api.chatMessages(activeId.value)
  await scrollToBottom()
}

async function selectConversation(id: string): Promise<void> {
  if (sending.value) return
  activeId.value = id
  lastDone.value = null
  await loadMessages()
}

async function newConversation(): Promise<void> {
  if (!stream.value || sending.value) return
  try {
    const conversation = await api.createConversation(stream.value.id)
    conversations.value = [conversation, ...conversations.value]
    activeId.value = conversation.id
    messages.value = []
    lastDone.value = null
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : '新建对话失败'
  }
}

async function load(): Promise<void> {
  loading.value = true
  error.value = null
  try {
    streams.value = await api.streams()
    if (!stream.value) {
      error.value = `还没有 ${symbol.value} 投资产品`
      return
    }
    conversations.value = await api.conversations(stream.value.id)
    if (conversations.value.length === 0) {
      const conversation = await api.createConversation(stream.value.id)
      conversations.value = [conversation]
    }
    activeId.value = conversations.value[0].id
    await loadMessages()
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : '对话加载失败'
  } finally {
    loading.value = false
  }
}

function handleEvent(event: ChatEvent): void {
  if (event.event === 'status') {
    statusText.value = event.data.message
  } else if (event.event === 'delta') {
    streamingText.value += event.data.text
    void scrollToBottom()
  }
}

async function send(text?: string): Promise<void> {
  const content = (text ?? input.value).trim()
  if (!content || sending.value || !activeId.value) return
  sending.value = true
  error.value = null
  statusText.value = '准备中…'
  streamingText.value = ''
  lastDone.value = null
  input.value = ''
  messages.value.push({
    id: `local-${Date.now()}`,
    seq: 9999,
    role: 'USER',
    content,
    status: 'COMPLETE',
    agent_run_id: null,
    sources: [],
    created_at: new Date().toISOString(),
  })
  await scrollToBottom()

  controller = new AbortController()
  const clientId =
    typeof crypto !== 'undefined' && 'randomUUID' in crypto
      ? crypto.randomUUID()
      : `${Date.now()}-${Math.random().toString(16).slice(2)}`
  try {
    lastDone.value = await streamChat(
      activeId.value,
      content,
      clientId,
      { onEvent: handleEvent },
      controller.signal,
    )
    statusText.value = ''
    await loadMessages()
    conversations.value = await api.conversations(stream.value!.id)
  } catch (caught) {
    if (caught instanceof DOMException && caught.name === 'AbortError') {
      statusText.value = '已停止生成'
    } else {
      error.value = caught instanceof Error ? caught.message : '回答失败'
    }
    await loadMessages().catch(() => undefined)
  } finally {
    sending.value = false
    controller = null
    streamingText.value = ''
  }
}

function stop(): void {
  controller?.abort()
}

function onComposerKeydown(event: KeyboardEvent): void {
  if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
    event.preventDefault()
    void send()
  }
}

onMounted(() => {
  void load()
})
</script>

<template>
  <section class="product-hero">
    <RouterLink class="back-link" :to="`/products/${symbol.toLowerCase()}`">
      ← 返回 {{ symbol }} 概览
    </RouterLink>
    <div class="product-title">
      <span class="product-symbol large">{{ symbol }}</span>
      <div>
        <p class="eyebrow">Conversation · read-only</p>
        <h1>投资对话</h1>
        <p class="muted">
          {{ stream?.name ?? '未配置' }} · 只读分析，不改 Thesis、不记成交、不下单
        </p>
      </div>
    </div>
    <button class="ghost-button" type="button" :disabled="sending" @click="newConversation">
      ＋ 新对话
    </button>
  </section>

  <div class="tabs">
    <RouterLink class="tab" :to="`/products/${symbol.toLowerCase()}`">概览</RouterLink>
    <RouterLink class="tab active" :to="`/products/${symbol.toLowerCase()}/chat`">对话</RouterLink>
    <RouterLink class="tab" :to="`/products/${symbol.toLowerCase()}/thesis`">投资论点</RouterLink>
  </div>

  <p v-if="error" class="error">
    {{ error }}
    <RouterLink v-if="error.includes('LLM')" class="inline-link" to="/settings">去 Settings 配置 LLM</RouterLink>
  </p>
  <p v-if="error?.includes('RATE_LIMITED')" class="error-hint">
    OKX 公共接口在限流，等待约 1 分钟后再试。
  </p>
  <p v-else-if="error?.includes('MARKET_UNAVAILABLE')" class="error-hint">
    OKX 行情不可达，通常是本机代理短暂断开或网络波动；对话需要行情上下文，恢复后重试即可。
  </p>

  <div v-if="!loading && stream" class="chat-layout">
    <aside class="chat-sidebar">
      <p class="eyebrow">Conversations</p>
      <ul>
        <li v-for="conversation in conversations" :key="conversation.id">
          <button
            class="conversation-button"
            :class="{ active: conversation.id === activeId }"
            type="button"
            @click="selectConversation(conversation.id)"
          >
            <strong>{{ conversation.title }}</strong>
            <small>{{ conversation.last_message ?? '还没有消息' }}</small>
          </button>
        </li>
      </ul>
      <p class="chat-sidebar-note">
        对话只读。要改观点，去 Thesis 编辑器；要记成交，去概览页的持仓面板。
      </p>
    </aside>

    <section class="chat-main">
      <div ref="scrollBox" class="chat-messages">
        <p v-if="loading" class="muted">加载对话…</p>
        <p v-else-if="messages.length === 0" class="chat-empty">
          <strong>{{ activeConversation?.title ?? '开始对话' }}</strong>
          <span>问价格、趋势、论点一致性，或者亏损时怎么按 if-then 处理。回答会标注数据来源与时间。</span>
        </p>

        <article
          v-for="message in messages"
          :key="message.id"
          class="chat-message"
          :class="message.role.toLowerCase()"
        >
          <header>
            <span class="chat-role">{{ message.role === 'USER' ? '你' : 'Thesium' }}</span>
            <span class="mono">{{ fmtTime(message.created_at) }}</span>
            <span v-if="message.status === 'PARTIAL'" class="priority-chip">未完成</span>
          </header>
          <div class="chat-content">{{ message.content }}</div>
          <div v-if="message.role === 'ASSISTANT'" class="chat-message-foot">
            <details v-if="message.sources.length" class="source-details">
              <summary>来源（{{ message.sources.length }}）</summary>
              <ul>
                <li v-for="source in message.sources" :key="source.tool">
                  <span class="mono">{{ source.tool }}</span>
                  <span>{{ source.label }} · {{ source.as_of ?? '—' }}</span>
                  <span v-if="source.staleness" class="muted">{{ source.staleness }}</span>
                </li>
              </ul>
            </details>
            <RouterLink
              v-if="message.agent_run_id"
              class="mono inline-link"
              :to="`/runs/${message.agent_run_id}`"
            >
              查看 Run 详情 →
            </RouterLink>
          </div>
        </article>

        <article v-if="streamingText" class="chat-message assistant streaming">
          <header>
            <span class="chat-role">Thesium</span>
            <span class="mono">生成中…</span>
          </header>
          <div class="chat-content">{{ streamingText }}</div>
        </article>

        <p v-if="statusText" class="chat-status muted">{{ statusText }}</p>
      </div>

      <div class="chat-composer">
        <div class="quick-prompts">
          <button
            v-for="prompt in quickPrompts"
            :key="prompt"
            class="quick-prompt"
            type="button"
            :disabled="sending"
            @click="send(prompt)"
          >
            {{ prompt }}
          </button>
        </div>
        <div class="composer-row">
          <textarea
            v-model="input"
            rows="2"
            placeholder="问一个问题… Enter 发送，Shift+Enter 换行"
            :disabled="sending"
            @keydown="onComposerKeydown"
          ></textarea>
          <button
            v-if="sending"
            class="ghost-button"
            type="button"
            @click="stop"
          >
            停止
          </button>
          <button v-else class="primary-button" type="button" :disabled="!input.trim()" @click="send()">
            发送
          </button>
        </div>
        <p class="form-note chat-disclaimer">
          只读建议，不构成投资建议；不会执行任何交易。模型可能出错，请核对来源与时间。
        </p>
      </div>
    </section>
  </div>
</template>