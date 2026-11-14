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
    throw new Error(`${response.status} ${response.statusText}`)
  }
  return (await response.json()) as T
}

export const api = {
  health: () => request<Health>('/health'),
  meta: () => request<Meta>('/api/v1/meta'),
  assets: () => request<Asset[]>('/api/v1/assets'),
  streams: () => request<Stream[]>('/api/v1/streams'),
  createStream: (payload: StreamCreate) =>
    request<Stream>('/api/v1/streams', {
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