export interface Health {
  status: string
  app: string
  version: string
  time: string
}

export interface Meta {
  name: string
  version: string
  environment: string
  phase: string
  capabilities: string[]
}

export interface Instrument {
  provider: string
  symbol: string
  market_type: string
  quote_currency: string
}

export interface Asset {
  id: string
  symbol: string
  name: string
  kind: string
  instruments: Instrument[]
}

export interface Quote {
  instrument: string
  price: string
  change_24h_pct: string | null
  high_24h: string | null
  low_24h: string | null
  volume_24h: string | null
  market_time: string
  fetched_at: string
  source: string
  staleness: string
}

export interface Candle {
  open_time: string
  open: string
  high: string
  low: string
  close: string
  volume: string
  confirmed: boolean
}

export interface TimeframeIndicators {
  status: string
  bars: number
  as_of: string | null
  close?: number | null
  ema20?: number | null
  ema50?: number | null
  rsi14?: number | null
  macd?: number | null
  macd_signal?: number | null
  macd_hist?: number | null
  volatility_pct?: number | null
  trend?: string
  warnings?: string[]
}

export interface Indicators {
  as_of: string | null
  timeframes: Record<string, TimeframeIndicators>
  warnings: string[]
}

export interface Derivatives {
  instrument: string
  mark_price: string
  funding_rate: string | null
  next_funding_time: string | null
  open_interest: string | null
  open_interest_usd: string | null
  market_time: string
  fetched_at: string
  source: string
  staleness: string
}

export interface MarketOverview {
  quote: Quote
  indicators: Indicators
  derivatives: Derivatives | null
  warnings: string[]
}

export interface StreamCreate {
  name: string
  asset_symbol: string
  provider: string
  instrument_symbol: string
  market_type: 'SPOT' | 'SWAP'
  timezone: string
  monitor_interval_minutes: number
  agent_enabled: boolean
}

export interface SpotState {
  quantity: string
  avg_cost: string
  realized_pnl: string
  fee_paid: string
}

export interface SpotMetrics {
  mark_price: string | null
  market_value: string | null
  unrealized_pnl: string | null
  unrealized_pnl_pct: string | null
  cost_basis: string
}

export interface SpotPortfolio {
  state: SpotState
  metrics: SpotMetrics
  version: number
}

export interface DerivativeState {
  side: 'LONG' | 'SHORT'
  quantity_base: string
  entry_price: string
  leverage: string
  margin: string
  liquidation_price: string | null
  realized_pnl: string
  funding_fees: string
}

export interface DerivativeMetrics {
  mark_price: string | null
  notional: string | null
  unrealized_pnl: string | null
  roe: string | null
  liq_distance_pct: string | null
  margin_ratio_pct: string | null
  effective_leverage: string | null
}

export interface DerivativePortfolio {
  state: DerivativeState
  metrics: DerivativeMetrics
  version: number
}

export interface Portfolio {
  spot: SpotPortfolio
  derivative: DerivativePortfolio | null
  warnings: string[]
}

export interface SpotEventInput {
  kind: 'BUY' | 'SELL' | 'OPENING' | 'CORRECTION'
  quantity: string
  price?: string
  avg_cost?: string
  fee?: string
  occurred_at: string
  note?: string
}

export interface DerivativeEventInput {
  kind: 'OPEN' | 'INCREASE' | 'REDUCE' | 'CLOSE' | 'ADJUST_MARGIN' | 'FUNDING' | 'CORRECTION'
  side?: 'LONG' | 'SHORT'
  quantity_base?: string
  price?: string
  leverage?: string
  margin_mode?: 'ISOLATED' | 'CROSS'
  margin?: string
  liquidation_price?: string
  fee?: string
  margin_delta?: string
  funding_amount?: string
  occurred_at: string
  note?: string
}

export interface PositionEvent {
  id: string
  kind: string
  side: string | null
  quantity: string | null
  price: string | null
  fee: string
  occurred_at: string
  note: string | null
}

export interface DerivativeEvent {
  id: string
  kind: string
  side: string
  quantity_base: string | null
  price: string | null
  fee: string
  occurred_at: string
  note: string | null
}

export interface LLMStatus {
  configured: boolean
  source: 'database' | 'environment' | 'none'
  base_url: string
  model: string
  has_api_key: boolean
  api_key_hint: string | null
  status: string
  last_tested_at: string | null
}

export interface LLMConfigUpdate {
  base_url: string
  model: string
  api_key?: string
  clear_api_key?: boolean
}

export interface EvidenceItem {
  claim: string
  kind: 'FACT' | 'INFERENCE'
  source_tool: string
  as_of: string | null
  strength: 'STRONG' | 'MODERATE' | 'WEAK'
}

export interface StopLossPlan {
  price: string
  source: 'USER' | 'DERIVED'
  risk_amount_usd: string | null
  risk_pct_equity: string | null
  distance_pct: string | null
  warnings: string[]
}

export interface DerivativeRecommendation {
  action: string
  size_change_pct: string | null
  rationale: string
  invalidation_conditions: unknown[]
  stop_loss: StopLossPlan | null
}

export interface Decision {
  id: string
  stream_id: string
  agent_run_id: string
  schema_version: string
  decision: string
  confidence: string
  priority: string
  summary: string
  evidence_for: EvidenceItem[]
  evidence_against: EvidenceItem[]
  thesis_alignment: {
    status: string
    explanation: string
    conflicting_fields: string[]
  }
  position_impact: {
    assessment: string
    exposure_usd: string | null
    unrealized_pnl_usd: string | null
    risk_budget_usage_pct: string | null
    notes: string | null
  }
  derivative_recommendation: DerivativeRecommendation | null
  changes_since_previous: unknown[]
  invalidation_conditions: unknown[]
  data_quality: {
    status: string
    missing: string[]
    staleness: string
    as_of: string | null
  }
  notification_recommendation: {
    notify: boolean
    reason: string | null
    suggested_priority: string | null
  }
  created_at: string
}

export interface AgentRun {
  id: string
  stream_id: string
  status: string
  task_type: string
  model: string | null
  prompt_version: string
  thesis_version_id: string | null
  position_snapshot_id: string | null
  derivative_snapshot_id: string | null
  market_snapshot_id: string | null
  input_digest: string | null
  input_context: Record<string, unknown> | null
  tool_calls: { tool: string; label: string; as_of: string | null }[]
  output_parsed: Record<string, unknown> | null
  latency_ms: number | null
  error_code: string | null
  error_message: string | null
  started_at: string
  finished_at: string | null
}

export interface StopLossPreviewInput {
  side: 'LONG' | 'SHORT'
  entry_price: string
  quantity_base: string
  account_equity_usd: string
  max_drawdown_pct: string
  max_concurrent_positions?: number
  max_risk_per_trade_pct?: string
  risk_budget_usd?: string
  explicit_stop?: string
  liquidation_price?: string
  fee_buffer_usd?: string
}

export interface StopLossPreviewResult {
  derived_stop: string
  explicit_stop: string | null
  effective_stop: string
  stop_source: 'USER' | 'DERIVED'
  risk_amount_usd: string
  risk_pct_equity: string
  per_trade_risk_pct: string
  risk_pct_source: string
  stop_distance_pct: string
  derived_stop_distance_pct: string
  loss_at_stop_usd: string
  within_budget: boolean
  liquidation_buffer_pct: string | null
  warnings: string[]
  assumptions: string[]
}

export interface AnalyzeResult {
  run: AgentRun
  decision: Decision
}

export interface ThesisDiffItem {
  op: string
  path: string
  before: unknown
  after: unknown
  classification: 'MATERIAL' | 'MINOR'
}

export interface ThesisVersion {
  id: string
  stream_id: string
  version: number
  status: 'PENDING_CONFIRMATION' | 'ACTIVE' | 'SUPERSEDED' | 'REJECTED'
  source: string
  change_class: 'MATERIAL' | 'MINOR'
  original_text: string
  final_text: string | null
  structured_content: Record<string, unknown>
  diff_from_previous: ThesisDiffItem[] | null
  confirmed_at: string | null
  effective_from: string
  effective_until: string | null
  created_at: string
}

export interface ThesisCreateInput {
  original_text: string
  final_text?: string
  structured_content: Record<string, unknown>
  source?: 'USER' | 'AGENT' | 'SYSTEM'
  base_version_id?: string
}

export interface ThesisPolishResult {
  polished_text: string
  change_notes: { kind: string; before: string; after: string; reason: string }[]
  warnings: string[]
  meaning_preserved: boolean
}

export interface ThesisParseResult {
  draft: Record<string, unknown>
  unparsed: { text: string; reason: string }[]
  clarifying_questions: string[]
  warnings: string[]
}

export interface Stream {
  id: string
  name: string
  status: string
  timezone: string
  monitor_interval_minutes: number
  agent_enabled: boolean
  created_at: string
  asset_symbol: string
  asset_name: string
  provider: string
  instrument_symbol: string
  market_type: string
}


export interface EmailStatus {
  configured: boolean
  host: string
  port: number
  username: string
  from_address: string
  to_address: string
  from_name: string
  use_tls: boolean
  use_ssl: boolean
  has_password: boolean
  status: string
  last_tested_at: string | null
  verified_at: string | null
}

export interface EmailConfigUpdate {
  host: string
  port: number
  from_address: string
  to_address?: string
  from_name?: string
  username?: string
  password?: string
  clear_password?: boolean
  use_tls: boolean
  use_ssl: boolean
}

export interface EmailTestResult {
  ok: boolean
  latency_ms?: number
  error?: string
  message?: string
  to?: string
}

export interface NotificationPreferences {
  decision_alert_enabled: boolean
  risk_alert_enabled: boolean
  email_enabled: boolean
  daily_summary_enabled: boolean
  quiet_hours_enabled: boolean
  quiet_hours_start: string
  quiet_hours_end: string
  daily_email_limit: number
  cooldown_minutes: number
  feishu_push_enabled: boolean
}

export interface NotificationDelivery {
  channel: string
  status: string
  attempts: number
  sent_at: string | null
  next_attempt_at: string | null
  last_error: string | null
}

export interface NotificationItem {
  id: string
  stream_id: string
  decision_id: string
  status: string
  decision: string
  alignment: string
  priority: string
  title: string
  body_text: string
  reason: string
  triggered_rules: string[]
  created_at: string
  deliveries: NotificationDelivery[]
}

export interface Conversation {
  id: string
  stream_id: string
  title: string
  status: string
  summary: string | null
  message_count?: number
  last_message?: string | null
  created_at: string
  updated_at: string
}

export interface ChatMessage {
  id: string
  seq: number
  role: 'USER' | 'ASSISTANT' | 'SYSTEM'
  content: string
  status: string
  agent_run_id: string | null
  sources: ChatSource[]
  created_at: string
}

export interface ChatSource {
  tool: string
  label: string
  as_of: string | null
  staleness?: string
}

export interface ChatDone {
  conversation_id: string
  message_id: string
  agent_run_id: string
  content: string
  sources: ChatSource[]
  guard_triggered: boolean
  latency_ms?: number
  replayed?: boolean
}

export type ChatEvent =
  | { event: 'meta'; data: Record<string, unknown> }
  | { event: 'status'; data: { message: string; stage?: string } }
  | { event: 'delta'; data: { text: string } }
  | { event: 'done'; data: ChatDone }
  | { event: 'error'; data: { code: string; message: string; status_code?: number } }

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: {
      Accept: 'application/json',
      ...(init?.body ? { 'Content-Type': 'application/json' } : {}),
      ...init?.headers,
    },
  })
  if (!response.ok) {
    const body = await response.json().catch(() => null)
    const message = body?.error?.message ?? `${response.status} ${response.statusText}`
    throw new Error(message)
  }
  return (await response.json()) as T
}

export const api = {
  health: () => request<Health>('/health'),
  meta: () => request<Meta>('/api/v1/meta'),
  assets: () => request<Asset[]>('/api/v1/assets'),
  streams: () => request<Stream[]>('/api/v1/streams'),
  previewStopLoss: (payload: StopLossPreviewInput) =>
    request<StopLossPreviewResult>('/api/v1/risk/stop-loss/preview', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  analyze: (streamId: string) =>
    request<AnalyzeResult>(`/api/v1/streams/${streamId}/analyze`, { method: 'POST' }),
  decisions: (streamId: string) =>
    request<Decision[]>(`/api/v1/streams/${streamId}/decisions`),
  emailStatus: () => request<EmailStatus>('/api/v1/settings/email'),
  saveEmailConfig: (payload: EmailConfigUpdate) =>
    request<EmailStatus>('/api/v1/settings/email', {
      method: 'PUT',
      body: JSON.stringify(payload),
    }),
  testEmail: (payload?: Partial<EmailConfigUpdate> & { recipient?: string }) =>
    request<EmailTestResult>('/api/v1/settings/email/test', {
      method: 'POST',
      ...(payload ? { body: JSON.stringify(payload) } : {}),
    }),
  notificationPreferences: () =>
    request<NotificationPreferences>('/api/v1/settings/notifications'),
  saveNotificationPreferences: (payload: NotificationPreferences) =>
    request<NotificationPreferences>('/api/v1/settings/notifications', {
      method: 'PUT',
      body: JSON.stringify(payload),
    }),
  notifications: (streamId?: string, limit = 30) =>
    request<NotificationItem[]>(
      `/api/v1/notifications?limit=${limit}${streamId ? `&stream_id=${streamId}` : ''}`,
    ),
  retryNotification: (notificationId: string) =>
    request<{ id: string; status: string; reason: string }>(
      `/api/v1/notifications/${notificationId}/retry`,
      { method: 'POST' },
    ),
  conversations: (streamId: string) =>
    request<Conversation[]>(`/api/v1/streams/${streamId}/conversations`),
  createConversation: (streamId: string, title?: string) =>
    request<Conversation>(`/api/v1/streams/${streamId}/conversations`, {
      method: 'POST',
      body: JSON.stringify({ title: title ?? null }),
    }),
  chatMessages: (conversationId: string, afterSeq?: number) =>
    request<ChatMessage[]>(
      `/api/v1/conversations/${conversationId}/messages${afterSeq ? `?after_seq=${afterSeq}` : ''}`,
    ),

  agentRuns: (streamId: string) =>
    request<AgentRun[]>(`/api/v1/streams/${streamId}/agent-runs`),
  agentRun: (runId: string) => request<AgentRun>(`/api/v1/agent-runs/${runId}`),
  llmStatus: () => request<LLMStatus>('/api/v1/settings/llm'),
  saveLlmConfig: (payload: LLMConfigUpdate) =>
    request<LLMStatus>('/api/v1/settings/llm', {
      method: 'PUT',
      body: JSON.stringify(payload),
    }),
  testLlm: (payload?: { base_url: string; model: string; api_key?: string }) =>
    request<{ ok: boolean; latency_ms?: number; error?: string; message?: string }>(
      '/api/v1/settings/llm/test',
      {
        method: 'POST',
        ...(payload ? { body: JSON.stringify(payload) } : {}),
      },
    ),
  thesis: (streamId: string) => request<ThesisVersion | null>(`/api/v1/streams/${streamId}/thesis`),
  thesisVersions: (streamId: string) =>
    request<ThesisVersion[]>(`/api/v1/streams/${streamId}/thesis/versions`),
  createThesis: (streamId: string, payload: ThesisCreateInput) =>
    request<{ version: ThesisVersion; requires_confirmation: boolean }>(
      `/api/v1/streams/${streamId}/thesis/versions`,
      { method: 'POST', body: JSON.stringify(payload) },
    ),
  confirmThesis: (versionId: string) =>
    request<ThesisVersion>(`/api/v1/thesis/versions/${versionId}/confirm`, { method: 'POST' }),
  rejectThesis: (versionId: string, reason?: string) =>
    request<ThesisVersion>(`/api/v1/thesis/versions/${versionId}/reject`, {
      method: 'POST',
      body: JSON.stringify({ reason: reason ?? null }),
    }),
  parseThesis: (streamId: string, text: string) =>
    request<ThesisParseResult>(`/api/v1/streams/${streamId}/thesis/parse`, {
      method: 'POST',
      body: JSON.stringify({ text }),
    }),
  polishThesis: (streamId: string, text: string) =>
    request<ThesisPolishResult>(`/api/v1/streams/${streamId}/thesis/polish`, {
      method: 'POST',
      body: JSON.stringify({ text }),
    }),
  createStream: (payload: StreamCreate) =>
    request<Stream>('/api/v1/streams', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  portfolio: (streamId: string) => request<Portfolio>(`/api/v1/streams/${streamId}/portfolio`),
  spotEvents: (streamId: string) =>
    request<PositionEvent[]>(`/api/v1/streams/${streamId}/position-events`),
  derivativeEvents: (streamId: string) =>
    request<DerivativeEvent[]>(`/api/v1/streams/${streamId}/derivative-position-events`),
  createSpotEvent: (streamId: string, payload: SpotEventInput) =>
    request<Portfolio>(`/api/v1/streams/${streamId}/position-events`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  createDerivativeEvent: (streamId: string, payload: DerivativeEventInput) =>
    request<Portfolio>(`/api/v1/streams/${streamId}/derivative-position-events`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  marketOverview: (symbol: string) =>
    request<MarketOverview>(`/api/v1/assets/${symbol}/market/overview`),
  candles: (symbol: string, timeframe: string, limit = 200) =>
    request<{ instrument: string; timeframe: string; candles: Candle[] }>(
      `/api/v1/assets/${symbol}/candles?timeframe=${timeframe}&limit=${limit}`,
    ),
}
export interface ChatStreamHandlers {
  onEvent?: (event: ChatEvent) => void
}

/**
 * POST an SSE chat turn and surface events as they arrive.
 *
 * EventSource cannot POST, so this uses fetch + ReadableStream. The server
 * closes the stream after a `done` or `error` event; `done` is also returned.
 */
export async function streamChat(
  conversationId: string,
  content: string,
  clientMessageId: string,
  handlers: ChatStreamHandlers = {},
  signal?: AbortSignal,
): Promise<ChatDone> {
  const response = await fetch(`/api/v1/conversations/${conversationId}/messages/stream`, {
    method: 'POST',
    headers: {
      Accept: 'text/event-stream',
      'Content-Type': 'application/json',
      'Idempotency-Key': clientMessageId,
    },
    body: JSON.stringify({ content, client_message_id: clientMessageId }),
    signal,
  })
  if (!response.ok) {
    const body = await response.json().catch(() => null)
    throw new Error(body?.error?.message ?? `${response.status} ${response.statusText}`)
  }
  if (!response.body) throw new Error('浏览器不支持流式响应')

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let done: ChatDone | null = null

  const handleBlock = (block: string): void => {
    let event = 'message'
    const dataLines: string[] = []
    for (const line of block.split('\n')) {
      if (line.startsWith('event:')) event = line.slice(6).trim()
      else if (line.startsWith('data:')) dataLines.push(line.slice(5).trim())
    }
    if (dataLines.length === 0) return
    const data = JSON.parse(dataLines.join('\n')) as Record<string, unknown>
    handlers.onEvent?.({ event, data } as ChatEvent)
    if (event === 'error') {
      throw new Error(String(data.message ?? '对话失败'))
    }
    if (event === 'done') done = data as unknown as ChatDone
  }

  try {
    while (true) {
      const { value, done: finished } = await reader.read()
      buffer += decoder.decode(value ?? new Uint8Array(), { stream: !finished })
      let boundary = buffer.indexOf('\n\n')
      while (boundary >= 0) {
        const block = buffer.slice(0, boundary)
        buffer = buffer.slice(boundary + 2)
        if (block.trim()) handleBlock(block)
        boundary = buffer.indexOf('\n\n')
      }
      if (finished) break
    }
    if (buffer.trim()) handleBlock(buffer)
  } finally {
    reader.releaseLock()
  }
  if (!done) throw new Error('对话流意外结束，请重试')
  return done
}
