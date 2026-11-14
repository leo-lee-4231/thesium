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
  status: string
  task_type: string
  model: string | null
  prompt_version: string
  latency_ms: number | null
  error_code: string | null
  error_message: string | null
  started_at: string
  finished_at: string | null
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
  analyze: (streamId: string) =>
    request<AnalyzeResult>(`/api/v1/streams/${streamId}/analyze`, { method: 'POST' }),
  decisions: (streamId: string) =>
    request<Decision[]>(`/api/v1/streams/${streamId}/decisions`),
  agentRuns: (streamId: string) =>
    request<AgentRun[]>(`/api/v1/streams/${streamId}/agent-runs`),
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