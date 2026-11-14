# 05 · REST API

> 状态：草案 v0.1
> 对应决策：D6（单租户）、D10（Headless 核心）、D14（只读对话）、D16（AI 润色）、D18（OKX）、D21（永续持仓）
> 约定：`/api/v1`；JSON；UTC ISO8601；金额/价格用字符串 Decimal；UUID。

---

## 1. 通用约定

### 1.1 格式

- Content-Type：`application/json`（SSE 除外）。
- 时间：`2026-11-14T15:00:00Z`；所有时间 UTC，前端按 Stream 时区展示。
- 金额/价格/数量：字符串，如 `"91240.00"`；禁止 JSON number 传输资金数值。
- 百分比：字符串或 number 均可，但需在 Schema 中固定；推荐字符串，如 `"42.0"`。
- ID：UUID v4。
- 分页：游标式 `?limit=50&cursor=...`；响应 `{ "items": [], "next_cursor": null }`。
- 空值：`null` 表示未知；不要用 `0` 冒充未知。

### 1.2 版本

- 路径版本 `/api/v1`；破坏性变更升 `/api/v2`。
- 新增字段向后兼容；前端忽略未知字段。
- OpenAPI 由 FastAPI 自动生成；前端类型用 `openapi-typescript` 生成。

### 1.3 幂等

需要幂等的写接口支持 `Idempotency-Key` 请求头（客户端生成 UUID）：

- `POST /streams/{id}/position-events`
- `POST /streams/{id}/derivative-position-events`
- `POST /streams/{id}/thesis/versions`
- `POST /conversations/{id}/messages`
- `POST /streams/{id}/analyze`

服务端保存 key + 响应 24 小时；重复请求返回相同响应，不重复写库。

---

## 2. 认证与暴露面

v1 单租户、无登录，但 API 仍必须防止被公网随意访问：

- 默认 `THESIUM_BIND_HOST=127.0.0.1`；Docker 只映射 `127.0.0.1:8000:8000`。
- 若绑定到非本地地址，必须设置 `THESIUM_ADMIN_TOKEN`；否则启动失败。
- 非本地请求需带 `X-Thesium-Token: <token>`；缺失/错误返回 401。
- 推荐公网访问方式：Tailscale / Cloudflare Tunnel + 反向代理认证，而不是直接暴露。
- CORS 默认只允许 `http://localhost:5173`（开发）与同源生产地址。
- 渠道（飞书）不经过公网 API，使用 Worker 内长连接；渠道绑定在 Web 设置页完成。

> 这是「单租户」不是「无安全」：没有登录态时，网络边界与 token 就是边界。

---

## 3. 错误格式

```json
{
  "error": {
    "code": "STALE_THESIS",
    "message": "当前 Thesis 已更新，请重新提交",
    "details": {"current_version": 4},
    "request_id": "req_01J..."
  }
}
```

| HTTP | code 示例 | 场景 |
|---|---|---|
| 400 | `INVALID_ARGUMENT` | 参数格式错误 |
| 401 | `UNAUTHORIZED` | 缺少/错误 admin token |
| 403 | `FORBIDDEN` | 跨 Stream 访问 |
| 404 | `NOT_FOUND` | 资源不存在 |
| 409 | `STALE_THESIS` / `CONFLICT` | 版本冲突、重复提交 |
| 422 | `VALIDATION_ERROR` | Schema 校验失败（含字段明细） |
| 429 | `RATE_LIMITED` | 超限，带 `Retry-After` |
| 502 | `LLM_UPSTREAM_ERROR` | 模型服务异常 |
| 503 | `DATA_UNAVAILABLE` | 行情/数据库不可用 |

---

## 4. 健康与元信息

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/health` | 进程存活；`{status, version, time}` |
| GET | `/ready` | 依赖就绪：DB、迁移版本；失败 503 |
| GET | `/version` | 构建信息（git sha、build time） |

---

## 5. 设置与 LLM Provider

### 5.1 用户设置

```http
GET /api/v1/settings
```

```json
{
  "user": {
    "id": "uuid",
    "email": "me@example.com",
    "display_name": "Leo",
    "timezone": "Asia/Shanghai"
  },
  "notification_preferences": {
    "decision_alert_enabled": true,
    "risk_alert_enabled": true,
    "daily_summary_enabled": false,
    "quiet_hours": {"start": "23:00", "end": "08:00"},
    "email_verified_at": "2026-11-14T10:00:00Z"
  }
}
```

```http
PATCH /api/v1/settings
{ "display_name": "Leo", "timezone": "Asia/Shanghai" }
```

### 5.2 邮箱验证

```http
POST /api/v1/settings/email/test
{ "email": "me@example.com" }
→ 202 { "status": "SENT" }
```

发送测试邮件；成功回调/手动确认后写 `email_verified_at`。v1 单用户，不做验证链接的复杂流程，但必须证明 SMTP 可用。

### 5.3 LLM Provider

v1 单租户只维护一个默认 Provider，通过设置接口读写；API Key 加密存储，只返回末 4 位。

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/settings/llm` | 当前配置与状态（不回显 Key） |
| PUT | `/settings/llm` | 保存 Base URL / Model / API Key；Key 留空表示不变 |
| POST | `/settings/llm/test` | 连接测试；可带未保存的 base_url/model/api_key，测试不写库 |

保存请求：

```json
{
  "base_url": "https://api.deepseek.com/v1",
  "model": "deepseek-chat",
  "api_key": "sk-...",
  "clear_api_key": false
}
```

状态响应：

```json
{
  "configured": true,
  "source": "database",
  "base_url": "https://api.deepseek.com/v1",
  "model": "deepseek-chat",
  "has_api_key": true,
  "api_key_hint": "…1234",
  "status": "OK",
  "last_tested_at": "2026-11-15T02:30:00Z"
}
```

测试响应：

```json
{"ok": true, "latency_ms": 820, "status_code": 200}
```

错误码：`LLM_NOT_CONFIGURED` / `LLM_TIMEOUT` / `LLM_UPSTREAM_ERROR` / `LLM_BAD_RESPONSE` / `SECRET_ERROR`。

---

## 6. Stream（UI: Investment Product）

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/streams` | 列表（含资产/行情标的） |
| POST | `/streams` | 创建（首版只允许一个 ACTIVE） |
| GET | `/streams/{id}` | 详情 |
| PATCH | `/streams/{id}` | 名称、监控间隔、agent_enabled |
| POST | `/streams/{id}/pause` | 暂停监控 |
| POST | `/streams/{id}/resume` | 恢复 |
| GET | `/streams/{id}/overview` | Dashboard 聚合 |

资产目录：

```http
GET /api/v1/assets
```

```json
[
  {
    "id": "uuid",
    "symbol": "BTC",
    "name": "Bitcoin",
    "kind": "CRYPTO",
    "instruments": [
      {"provider": "okx", "symbol": "BTC-USDT", "market_type": "SPOT", "quote_currency": "USDT"},
      {"provider": "okx", "symbol": "BTC-USDT-SWAP", "market_type": "SWAP", "quote_currency": "USDT"}
    ]
  }
]
```

资产级行情（P1 先实现，不依赖 Stream）：

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/assets/{symbol}/market?market_type=SPOT` | 报价 + 数据质量 |
| GET | `/assets/{symbol}/candles?timeframe=1h&limit=200` | K 线；`limit<=300` |
| GET | `/assets/{symbol}/indicators?timeframes=1h,4h,1d` | 指标快照 |
| GET | `/assets/{symbol}/derivatives` | SWAP mark/funding/OI |
| GET | `/assets/{symbol}/market/overview` | 报价 + 三周期指标 + 衍生品观察（详情页用） |

Stream 级行情接口在 P2 产品上下文稳定后再补，避免重复实现。

创建请求：

```json
{
  "name": "BTC 长期配置",
  "asset_symbol": "BTC",
  "instrument": {
    "provider": "okx",
    "symbol": "BTC-USDT",
    "market_type": "SPOT"
  },
  "timezone": "Asia/Shanghai",
  "monitor_interval_minutes": 60,
  "agent_enabled": true
}
```

创建响应 `201`：Stream + seed 的 Asset/Instrument。

首版限制：同一用户只允许一个 `ACTIVE` Stream；违反返回 `409 STREAM_LIMIT`。数据库不建唯一约束，留给未来。

主标的：v1 只允许 `market_type=SPOT`；SWAP 作为同一产品的合约观察/持仓数据自动加载，不作为第二个产品。

`GET /streams/{id}/overview`：

```json
{
  "stream": {"id": "uuid", "name": "BTC 长期配置", "status": "ACTIVE"},
  "asset": {"symbol": "BTC", "name": "Bitcoin"},
  "market": {
    "price": "91240.00",
    "change_24h_pct": "1.80",
    "market_time": "2026-11-14T15:00:00Z",
    "fetched_at": "2026-11-14T15:00:12Z",
    "staleness": "FRESH"
  },
  "position": {
    "quantity": "0.50000000",
    "avg_cost": "82000.00",
    "market_value": "45620.00",
    "unrealized_pnl": "4620.00"
  },
  "derivative_position": {
    "side": "LONG",
    "quantity_base": "0.20000000",
    "entry_price": "88000.00",
    "leverage": "3",
    "margin": "6000.00",
    "liquidation_price": "65000.00",
    "unrealized_pnl": "648.00",
    "liq_distance_pct": "28.76"
  },
  "derivatives_market": {
    "mark_price": "91240.00",
    "funding_rate": "0.0001",
    "open_interest": "12345.67",
    "as_of": "2026-11-14T15:00:00Z"
  },
  "thesis": {
    "version": 3,
    "status": "ACTIVE",
    "effective_from": "2026-11-10T09:00:00Z"
  },
  "latest_decision": {
    "id": "uuid",
    "decision": "WAIT",
    "priority": "NORMAL",
    "created_at": "2026-11-14T14:00:00Z"
  }
}
```

---

## 7. 行情与指标

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/streams/{id}/market` | 最新报价 + 数据质量 |
| GET | `/streams/{id}/market/candles?timeframe=1h&limit=200` | K 线；`limit<=300` |
| GET | `/streams/{id}/market/indicators?timeframes=1h,4h,1d` | 指标快照 |
| GET | `/streams/{id}/market/derivatives` | SWAP mark/funding/open interest（观察） |

K 线响应：

```json
{
  "instrument": {"provider": "okx", "symbol": "BTC-USDT", "timeframe": "1h"},
  "candles": [
    {"open_time": "2026-11-14T14:00:00Z", "open": "91000.0", "high": "91400.0", "low": "90800.0", "close": "91240.0", "volume": "123.45"}
  ],
  "coverage": {"from": "2026-11-06T15:00:00Z", "to": "2026-11-14T15:00:00Z"},
  "staleness": "FRESH"
}
```

指标响应：

```json
{
  "as_of": "2026-11-14T15:00:00Z",
  "timeframes": {
    "1h": {"rsi14": "58.2", "ema20": "89800.0", "macd_hist": "120.0"},
    "4h": {"rsi14": "51.0", "ema20": "88500.0", "macd_hist": "80.0"},
    "1d": {"trend": "UP", "rsi14": "62.0"}
  },
  "staleness": "FRESH"
}
```

衍生品观察：

```json
{
  "instrument": {"provider": "okx", "symbol": "BTC-USDT-SWAP", "market_type": "SWAP"},
  "mark_price": "91260.00",
  "funding_rate": "0.0001",
  "next_funding_time": "2026-11-14T16:00:00Z",
  "open_interest": "12345.67",
  "market_time": "2026-11-14T15:00:00Z",
  "fetched_at": "2026-11-14T15:00:12Z",
  "staleness": "FRESH"
}
```

---

## 8. Investment Thesis

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/streams/{id}/thesis` | 当前 ACTIVE |
| GET | `/streams/{id}/thesis/versions` | 版本列表 |
| GET | `/thesis/versions/{id}` | 版本详情 |
| GET | `/thesis/versions/{id}/diff?against={other_id}` | 版本对比 |
| POST | `/streams/{id}/thesis/parse` | AI 整理，返回草案（不落库） |
| POST | `/streams/{id}/thesis/polish` | AI 润色，返回建议（不落库） |
| POST | `/streams/{id}/thesis/versions` | 提交新版本 |
| PATCH | `/thesis/versions/{id}` | 编辑 PENDING 版本 |
| POST | `/thesis/versions/{id}/confirm` | 确认 MATERIAL |
| POST | `/thesis/versions/{id}/reject` | 拒绝 PENDING |

### 8.1 解析

```http
POST /api/v1/streams/{id}/thesis/parse
{
  "original_text": "我认为 BTC 短期可能转空，预计回调至 65,000 附近；但中长期依然看涨……"
}
```

响应 `200`：

```json
{
  "draft": {"schema_version": "1.0", "market_outlook": {"short_term": "BEARISH"}},
  "unparsed": [],
  "clarifying_questions": ["你说的「短期」大概是指几周？"],
  "warnings": ["补充失效条件会更完整"],
  "agent_run_id": "uuid"
}
```

不落库；编辑器回填后由用户提交。

### 8.2 润色

```http
POST /api/v1/streams/{id}/thesis/polish
{
  "text": "我认为 BTC 短期可能转空，预计回调至 65000 附近，但长期还是看涨"
}
```

响应 `200`：

```json
{
  "polished_text": "我认为 BTC 短期可能转空，预计回调至 65,000 附近；但中长期依然看涨。",
  "change_notes": [
    {
      "kind": "CLARITY",
      "before": "65000",
      "after": "65,000",
      "reason": "统一数字格式"
    }
  ],
  "warnings": [],
  "meaning_preserved": true,
  "agent_run_id": "uuid"
}
```

- 不落库；用户点击「采用润色」或手动编辑后才进入提交。
- 数字、方向、否定关系发生变化时返回 `warnings`，前端高亮，需用户确认。
- 润色只允许在编辑器触发；对话接口不提供该能力。

### 8.3 提交

```http
POST /api/v1/streams/{id}/thesis/versions
{
  "original_text": "……",
  "final_text": "……",
  "structured_content": {"...": "..."},
  "source": "USER",
  "source_agent_run_id": "uuid|null",
  "polish_agent_run_id": "uuid|null",
  "base_version_id": "uuid|null"
}
```

- `original_text`：用户原始输入，必填。
- `final_text`：用户确认正文（可为润色版），可空；为空时后端回退到 `original_text`。
- `MATERIAL` → `201`，`status=PENDING_CONFIRMATION`，返回 diff。
- `MINOR` → `201`，`status=ACTIVE`。
- `base_version_id` 与当前 ACTIVE 不一致 → `409 STALE_THESIS`。

响应：

```json
{
  "version": {
    "id": "uuid",
    "version": 4,
    "status": "PENDING_CONFIRMATION",
    "change_class": "MATERIAL",
    "original_text": "……",
    "final_text": "……",
    "diff": [
      {"op": "replace", "path": "/market_outlook/short_term", "before": "NEUTRAL", "after": "BEARISH", "classification": "MATERIAL"}
    ]
  },
  "requires_confirmation": true
}
```

### 8.4 确认 / 拒绝

```http
POST /api/v1/thesis/versions/{id}/confirm
→ 200 { "version": { "version": 4, "status": "ACTIVE" } }
```

```http
POST /api/v1/thesis/versions/{id}/reject
{ "reason": "再想想" }
→ 200 { "version": { "version": 4, "status": "REJECTED" } }
```

确认时若已有更新版本 ACTIVE → `409 STALE_THESIS`。

---

## 9. 持仓（现货 + USDT 永续）

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/streams/{id}/positions` | 当前现货持仓快照 |
| GET | `/streams/{id}/position-events` | 现货事件时间线 |
| POST | `/streams/{id}/position-events` | 记录现货成交 / 修正 |
| GET | `/streams/{id}/position-snapshots` | 现货不可变快照列表 |
| POST | `/streams/{id}/positions/simulate` | 现货只读情景计算 |
| GET | `/streams/{id}/derivative-positions` | 当前永续持仓 |
| GET | `/streams/{id}/derivative-position-events` | 永续事件时间线 |
| POST | `/streams/{id}/derivative-position-events` | 开/加/减/平/调保证金/修正 |
| GET | `/streams/{id}/derivative-position-snapshots` | 永续不可变快照列表 |
| POST | `/streams/{id}/derivative-positions/simulate` | 永续只读情景计算 |

### 9.1 记录成交

```http
POST /api/v1/streams/{id}/position-events
Idempotency-Key: 7b1c...
{
  "kind": "BUY",
  "quantity": "0.20000000",
  "price": "92000.00",
  "fee": "5.00",
  "occurred_at": "2026-11-14T15:10:00Z",
  "note": "手动补录"
}
```

响应 `201`：

```json
{
  "event": {"id": "uuid", "kind": "BUY", "quantity": "0.2", "price": "92000.00", "occurred_at": "..."},
  "position": {"quantity": "0.70000000", "avg_cost": "84857.14", "version": 4},
  "snapshot_id": "uuid"
}
```

### 9.2 修正持仓

```http
POST /api/v1/streams/{id}/position-events
{
  "kind": "CORRECTION",
  "quantity": "0.50000000",
  "avg_cost": "82000.00",
  "occurred_at": "2026-11-14T15:20:00Z",
  "reason": "交易所实际余额与记录不一致"
}
```

必须记录 `before_state` / `after_state`；不允许静默覆盖。

### 9.3 情景模拟（只读）

```http
POST /api/v1/streams/{id}/positions/simulate
{
  "side": "SELL",
  "quantity": "0.20000000",
  "assumed_price": "92000.00"
}
→ 200 {
  "before": {"quantity": "0.7", "exposure": "63868.00"},
  "after": {"quantity": "0.5", "exposure": "45620.00", "realized_pnl": "2000.00"},
  "risk_budget_usage_pct": "30.0"
}
```

不落库；对话的 `simulate_position_change` 复用同一服务。

### 9.4 记录永续持仓

```http
POST /api/v1/streams/{id}/derivative-position-events
Idempotency-Key: 3c9...
{
  "kind": "OPEN",
  "side": "LONG",
  "quantity_base": "0.20000000",
  "price": "88000.00",
  "leverage": "3",
  "margin_mode": "ISOLATED",
  "margin": "6000.00",
  "liquidation_price": "65000.00",
  "fee": "2.50",
  "occurred_at": "2026-11-14T15:10:00Z"
}
```

响应 `201`：

```json
{
  "position": {
    "id": "uuid",
    "side": "LONG",
    "quantity_base": "0.20000000",
    "entry_price": "88000.00",
    "leverage": "3",
    "margin": "6000.00",
    "liquidation_price": "65000.00",
    "version": 1
  },
  "snapshot": {
    "id": "uuid",
    "mark_price": "91240.00",
    "unrealized_pnl": "648.00",
    "roe": "10.8",
    "liq_distance_pct": "28.76"
  }
}
```

规则：

- 只支持 `LONG` / `SHORT` 单向；已有相反方向持仓 → `409 POSITION_SIDE_CONFLICT`。
- `liquidation_price` 是用户从交易软件录入的值，服务端不估算；可空，但为空时风险字段为 `null`。
- `kind`：`OPEN` / `INCREASE` / `REDUCE` / `CLOSE` / `ADJUST_MARGIN` / `FUNDING` / `CORRECTION`。
- 修正必须带 `before_state` / `after_state`，不允许静默覆盖。

### 9.5 永续情景模拟（只读）

```http
POST /api/v1/streams/{id}/derivative-positions/simulate
{
  "action": "REDUCE_LONG",
  "size_change_pct": "25",
  "assumed_mark": "90000.00"
}
→ 200 {
  "before": {"quantity_base": "0.2", "unrealized_pnl": "648.00", "liq_distance_pct": "28.76"},
  "after": {"quantity_base": "0.15", "unrealized_pnl": "486.00", "liq_distance_pct": "28.76"},
  "margin": "6000.00"
}
```

不落库；不返回估算清算价，只返回用户录入清算价下的距离。

---

## 10. Decision 与 Run

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/streams/{id}/decisions` | 时间线 |
| GET | `/decisions/{id}` | 单条详情 |
| GET | `/agent-runs/{id}` | Run 详情（版本、工具、usage） |
| GET | `/streams/{id}/agent-runs` | Run 列表（可按 task_type 过滤） |
| POST | `/streams/{id}/analyze` | 按需触发一次监控分析 |

`POST /analyze` 返回 `202`：

```json
{"job_id": "uuid", "status": "QUEUED"}
```

前端轮询 `GET /agent-runs?job_id=` 或 `GET /jobs/{id}`（若暴露）。

---

## 11. 对话

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/streams/{id}/conversations` | 会话列表 |
| POST | `/streams/{id}/conversations` | 创建 Web 会话（若已存在 OPEN 则返回） |
| GET | `/conversations/{id}` | 会话详情 |
| GET | `/conversations/{id}/messages?before_seq=&limit=50` | 消息历史 |
| POST | `/conversations/{id}/messages` | 发送消息；SSE 流式响应 |
| POST | `/conversations/{id}/archive` | 归档 |

### 11.1 发送消息（SSE）

```http
POST /api/v1/conversations/{id}/messages
Accept: text/event-stream
Idempotency-Key: 9f2...
Content-Type: application/json

{ "content": "BTC 现在什么价？我的论点还成立吗？" }
```

响应 `200 Content-Type: text/event-stream`：

```text
event: meta
data: {"conversation_id":"...","user_message_id":"..."}

event: status
data: {"stage":"collecting_context"}

event: tool
data: {"name":"get_asset_overview","status":"ok","as_of":"2026-11-14T15:00:00Z"}

event: delta
data: {"text":"当前 BTC 报价 91,240 USDT（15:00 UTC）"}

event: done
data: {"message_id":"...","agent_run_id":"...","usage":{"input_tokens":3120,"output_tokens":410}}
```

- 客户端断开后，服务端继续完成并落库；重连用 `GET messages?after_seq=` 补齐。
- 若 `Accept` 不是 SSE，返回 `200` JSON 完整消息（便于脚本/测试）。
- 首 token 超时 30s，整轮 90s；超时发 `error` 并落库错误消息。
- 只读：响应中不会出现「已修改」；若模型输出违规，由校验替换。

### 11.2 消息结构

```json
{
  "id": "uuid",
  "seq": 12,
  "role": "ASSISTANT",
  "content": "……",
  "created_at": "2026-11-14T15:01:00Z",
  "agent_run_id": "uuid",
  "provenance": {
    "thesis_version": 3,
    "market_as_of": "2026-11-14T15:00:00Z",
    "tools": ["get_asset_overview", "get_investment_thesis"],
    "staleness": "FRESH"
  }
}
```

`provenance` 由服务端生成，不由模型输出。

---

## 12. 通知

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/streams/{id}/notifications` | 通知记录 |
| GET | `/notifications/{id}` | 详情 + deliveries |
| POST | `/notifications/{id}/retry` | 手动重试（仅 FAILED） |

---

## 13. 渠道（v1.1）

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/channels/bindings` | 当前绑定 |
| POST | `/channels/feishu/pairing-code` | 生成配对码（10 分钟） |
| DELETE | `/channels/bindings/{id}` | 撤销 |
| GET | `/channels/deliveries` | 投递记录 |
| POST | `/channels/simulate` | 开发环境模拟入站（仅 DEBUG） |

配对码响应：

```json
{
  "code": "7K2M9Q",
  "expires_at": "2026-11-14T15:20:00Z",
  "instructions": "在飞书机器人中发送 /bind 7K2M9Q"
}
```

---

## 14. Proposal（v1.2+ 预留）

v1.0 不产生 Proposal；以下接口先定义、不实现：

| 方法 | 路径 |
|---|---|
| GET | `/streams/{id}/proposals` |
| GET | `/proposals/{id}` |
| POST | `/proposals/{id}/confirm` |
| POST | `/proposals/{id}/reject` |

---

## 15. 限流

| 接口 | 限制 |
|---|---|
| 对话消息 | 10/min，100/day |
| Thesis 解析 | 10/hour |
| 按需分析 | 4/hour |
| 持仓写入 | 60/day |
| 渠道入站 | 20/min/binding |

超限返回 `429` + `Retry-After`。

---

## 16. 前端类型

```bash
# backend 生成 openapi.json
uv run python -m app.scripts.export_openapi > openapi.json

# frontend 生成类型
pnpm openapi-typescript ../openapi.json -o src/api/schema.d.ts
```

CI 校验生成的类型与提交版本一致，避免前后端漂移。

---

## 17. 开放问题

| # | 问题 | 当前默认 |
|---|---|---|
| A1 | 是否暴露 `/jobs/{id}` 给前端轮询？ | v1 用 `agent_run_id` 轮询 |
| A2 | 对话消息是否允许编辑/删除？ | 不允许；只归档会话 |
| A3 | 是否支持多 Stream API？ | 领域支持，v1 UI 限制一个 |
| A4 | 是否提供 OpenAPI 文档页？ | 开发环境 `/docs`，生产关闭 |
| A5 | 是否支持批量导入成交？ | v1 不做 |