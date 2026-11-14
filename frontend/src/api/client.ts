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

async function request<T>(path: string): Promise<T> {
  const response = await fetch(path, {
    headers: { Accept: 'application/json' },
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
}