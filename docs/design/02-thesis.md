# 02 · Investment Thesis

> 状态：草案 v0.1
> 对应决策：D4（分级确认）、D13（对话记忆边界）、D14（正式变更边界）、D16（AI 润色）、D21（永续约束）
> 一句话：**用户原话是事实，结构化内容是整理；AI 可以整理，不能替用户改口。**

---

## 1. 定位

Investment Thesis 统一承载用户对某个资产的目标、观点与约束，代替过去分散的「投资计划 + 市场观点」两个模块。

它必须同时满足三件事：

1. **低门槛**：用户只写一段自然语言也能用；不强迫理解 RSI/MACD。
2. **可审计**：每次变更是一个新版本，原话不丢，旧版本可查。
3. **可计算**：结构化字段可被 Agent 和程序读取，用于一致性判断、风险提示和决策上下文。

边界：

- Thesis 是**用户观点**，不是市场事实，也不是 AI 推断。
- Thesis 不是持仓；持仓由 Portfolio 子域独立维护。
- Thesis 不是聊天记录；对话内容不会自动进入 Thesis。
- Thesis 不是策略回测配置；v1 不支持程序化规则。

---

## 2. 结构化内容 Schema

`investment_theses.structured_content` 使用 JSON；金额/价格用**字符串**保存，应用层转 `Decimal`。

### 2.1 示例

```json
{
  "schema_version": "1.0",
  "thesis_statement": "短期可能回调至 65,000，中长期看涨；不因短期下跌清仓",
  "purpose": "长期配置，同时保留部分波段操作空间",
  "time_horizon": {
    "short_term": "WEEKS",
    "medium_term": "MONTHS",
    "long_term": "YEARS"
  },
  "market_outlook": {
    "short_term": "BEARISH",
    "medium_term": "NEUTRAL",
    "long_term": "BULLISH"
  },
  "scenarios": [
    {
      "id": "S1",
      "direction": "DOWN",
      "target_price": "65000",
      "target_currency": "USDT",
      "time_horizon": "SHORT_TERM",
      "status": "USER_EXPECTATION",
      "conditions": ["跌破 70,000 后成交量放大"],
      "invalidation": "周线重新站上 95,000"
    }
  ],
  "key_levels": {
    "support": ["64000", "70000"],
    "resistance": ["95000"],
    "watch": ["88000"]
  },
  "risk": {
    "account_equity_usd": "20000",
    "max_drawdown_pct": "20",
    "max_position_pct": "50",
    "max_risk_per_trade_pct": "2",
    "max_concurrent_positions": "3",
    "risk_budget_usd": "10000",
    "stop_loss_price": null,
    "take_profit_price": null
  },
  "position_intent": {
    "preferred_position_pct": "30",
    "allow_add": true,
    "allow_reduce": true,
    "avoid_full_exit": true
  },
  "derivative_intent": {
    "allow_perpetual": true,
    "allow_short": false,
    "max_leverage": "2",
    "max_margin_usd": "2000",
    "min_liquidation_buffer_pct": "30",
    "long_stop_loss_price": null,
    "short_stop_loss_price": "95000"
  },
  "constraints": [
    "不希望仅因短期下跌而完全离场",
    "不使用超过 2 倍杠杆"
  ],
  "open_questions": [
    "如果跌破 60,000，论点是否仍然成立？"
  ],
  "notes": "目前更关注宏观流动性，而不是链上数据。"
}
```

### 2.2 字段说明

| 字段 | 类型 | 说明 | 空值 |
|---|---|---|---|
| `schema_version` | string | Schema 版本 | 必填 |
| `thesis_statement` | string | 一句话论点摘要，来自用户原话或用户确认的整理 | 可空字符串 |
| `purpose` | string \| null | 投资目的（长期配置/波段/观察） | 可空 |
| `time_horizon` | object | 短/中/长期的时间单位 | 可空对象 |
| `market_outlook` | object | 短/中/长期方向 | 可空对象 |
| `scenarios` | array | 用户预期的情景与目标价 | 可为空数组 |
| `key_levels` | object | 关注价位（支撑/阻力/观察） | 可为空 |
| `risk` | object | 风险预算与限制 | 可为空 |
| `position_intent` | object | 仓位意图，不是当前持仓 | 可为空 |
| `derivative_intent` | object | 永续意图：是否允许、是否允许做空、最大杠杆/保证金、最低清算缓冲、做多/做空硬止损 | 可为空 |
| `constraints` | string[] | 投资约束（自然语言） | 可为空数组 |
| `open_questions` | string[] | 用户当前关注的问题 | 可为空数组 |
| `notes` | string \| null | 补充说明 | 可空 |

枚举：

- `time_horizon.*`：`DAYS` / `WEEKS` / `MONTHS` / `YEARS`
- `market_outlook.*`：`BULLISH` / `NEUTRAL` / `BEARISH` / `UNCERTAIN`
- `scenarios[].direction`：`UP` / `DOWN` / `RANGE`
- `scenarios[].time_horizon`：`SHORT_TERM` / `MEDIUM_TERM` / `LONG_TERM`
- `scenarios[].status`：`USER_EXPECTATION` / `CONDITIONAL`

### 2.4 原文、确认正文与结构化字段的关系

| 字段 | 是什么 | 谁读它 | 作用 |
|---|---|---|---|
| `original_text` | 用户原始输入，逐版本留底 | 审计 / 历史对比 | 保留用户原话，不被覆盖 |
| `final_text` | 用户确认后的正文（可润色/编辑） | Agent 分析、对话 | 提供完整语义、语境、条件与细节 |
| `structured_content` | 对原文的可计算摘要 | 程序校验、Agent 分析 | 方向/周期/目标价/风险/杠杆等硬约束，以及 MATERIAL/MINOR 分类 |

原则：

- **两者都进入上下文**：P4 的监控分析会同时读取 `final_text` 与 `structured_content`；
  前者解释「为什么」，后者提供可计算、可校验的约束。
- **冲突时不能静默取一个**：若文字说看涨、结构化写 BEARISH，Agent 应标记冲突并要求 `REVIEW`，
  而不是自行选择。P4 会在 Prompt 与 Validator 里落实。
- **结构化字段不替代原文**：它是有损摘要；原文中的条件、例外和语气不能被丢掉。
- **允许留空**：观察型或纯文字 Thesis 可以只有 `final_text`，但 Agent 无法做严格的
  方向/风险/杠杆约束校验。
- **分类只看结构化 diff**：当前 `MATERIAL/MINOR` 由 `structured_content` 的变化决定；
  如果只改文字、不改 JSON，可能被归为 MINOR。改变观点时应同时更新 JSON，或重新执行 AI 整理。

### 2.3 设计约束

- **不发明数字**：用户没说目标价，`target_price` 就是 `null`；用户没说风险预算，`risk` 字段留空。
- **不发明方向**：用户没说长期看涨，`long_term` 就是 `UNCERTAIN`，不是默认 `BULLISH`。
- **原文优先**：`thesis_statement` 是对原话的压缩，不是新策略；`original_text` 永远保留。
- **position_intent ≠ position**：这里写「希望仓位 30%」，不代表真实持仓 30%；真实持仓在 Portfolio。
- **可空**：观察型 Stream 可以只有 `original_text`，`structured_content` 为 `{}`。

---

### 2.5 风险参数、硬止损与推导止损

`risk` 里有两类东西，不能混为一谈：

| 字段 | 含义 | 用途 |
|---|---|---|
| `account_equity_usd` | 可管理的总权益（USDT） | 计算单笔风险金额 |
| `max_drawdown_pct` | 组合级最大可接受回撤 | 组合护栏，不是单笔止损 |
| `max_risk_per_trade_pct` | 单笔最大风险占比 | 优先使用；未填则用最大回撤 / 并行笔数 |
| `max_concurrent_positions` | 最多同时持有几笔策略 | 推导单笔风险时的分母 |
| `risk_budget_usd` | 绝对风险预算 | 与比例风险取较小值 |
| `risk.stop_loss_price` | 当前/整体硬止损 | 用户明确指定时使用 |
| `derivative_intent.long_stop_loss_price` | 永续多头的用户硬止损 | 用户明确指定时使用 |
| `derivative_intent.short_stop_loss_price` | 永续空头的用户硬止损 | 用户明确指定时使用 |

关键区分：

- **用户硬止损**是输入，存进 Thesis；方向必须正确（多头止损 < 开仓价，空头止损 > 开仓价）。
- **推导止损**是输出，不进 Thesis；由程序按风险预算计算，写入 Decision/策略建议，并标注 `source=DERIVED`。
- 推导公式（USDT 本位永续，线性）：
  - 单笔风险 = `min(权益 × 单笔风险%, 绝对风险预算)`
  - 止损距离 = `单笔风险 / 数量`
  - 多头止损 = `开仓价 - 距离`；空头止损 = `开仓价 + 距离`
  - 同时校验：多头止损必须高于清算价，空头止损必须低于清算价。
- **最大回撤不能直接当单笔止损**。它描述的是组合从高点到低点的容忍度；单笔止损还需要单笔风险比例（或按并行笔数推导的假设）。否则一次交易就可能吃掉全部回撤预算。
- **当前默认（2026-11-15 确认）**：未填 `max_risk_per_trade_pct` 时，单笔风险 = `max_drawdown_pct / max_concurrent_positions`；`max_concurrent_positions` 未填时按 5 笔计算，并在结果的 `assumptions` 中明确标注。
- 如果用户给了硬止损但对应亏损超过单笔风险预算，程序必须提示冲突，不能静默采用。

## 3. MATERIAL 与 MINOR

### 3.1 判定表

| 路径 | 分类 | 理由 |
|---|---|---|
| `market_outlook.*` | **MATERIAL** | 方向改变会直接改变建议语义 |
| `time_horizon.*` | **MATERIAL** | 周期改变会改变「等待」还是「行动」 |
| `scenarios` 增删、`target_price`、`direction`、`time_horizon` | **MATERIAL** | 目标价是决策锚点 |
| `scenarios[].status` 改为 `INVALIDATED` | **MATERIAL** | 情景失效需要重新审视 |
| `risk.*` | **MATERIAL** | 风险预算是硬约束 |
| `position_intent.*` | **MATERIAL** | 仓位意图影响加减仓建议 |
| `derivative_intent.*` | **MATERIAL** | 永续杠杆/保证金/做空权限是硬约束 |
| `constraints` 增删改 | **MATERIAL** | 约束是用户明确边界 |
| `thesis_statement` 改写 | MINOR | 摘要措辞，除非引入新的方向/价位（需重新解析） |
| `key_levels` | MINOR | 观察价位，不直接构成交易指令 |
| `purpose` / `notes` / `open_questions` | MINOR | 补充信息 |
| `structured_content` 从 `{}` 变为有值 | 按实际路径判定 | 观察型转正式观点 |

规则：

1. 先对 `structured_content` 做结构化 diff，命中的路径按表分类。
2. 任一 MATERIAL 字段变化 → 整个版本 `change_class = MATERIAL`。
3. 无 MATERIAL 变化 → `MINOR`。
4. **不确定时按 MATERIAL 处理**（安全默认）。
5. AI 解析若把「未识别段落」标记为包含方向/价位/风险，强制 MATERIAL 并要求澄清。
6. 用户只改 `original_text`、结构化内容不变 → `MINOR`（原文补充），但会保留旧版本。

### 3.2 确认规则

| change_class | 提交后状态 | 是否需要再次确认 | 生效方式 |
|---|---|---|---|
| `MATERIAL` | `PENDING_CONFIRMATION` | 是：展示 diff，点击「确认生效」 | 确认后原子切换 ACTIVE |
| `MINOR` | `ACTIVE` | 否 | 提交即生效，旧版本 SUPERSEDED |

补充：

- 即使是用户自己提交的 MATERIAL 变更，也要经过 diff 确认页；这是为了防止误触与「AI 整理后直接生效」。
- Agent 永远不能调用「确认」；确认接口只接受用户会话/本地管理令牌。
- 拒绝的版本保留为 `REJECTED`，不删除；下一次提交生成新版本号。
- 同一 Stream 同时只允许一个 `PENDING_CONFIRMATION`；新草案创建时，旧草案自动 `REJECTED`，备注「被新草案替代」。
- 确认时若当前 ACTIVE 版本已不是提交时的基准版本，返回 `409 STALE_THESIS`，要求重新提交（不做自动合并）。

---

## 4. 版本状态机

```mermaid
stateDiagram-v2
    [*] --> PENDING_CONFIRMATION : MATERIAL 提交（含 AI 整理后提交）
    [*] --> ACTIVE : MINOR 提交
    PENDING_CONFIRMATION --> ACTIVE : 用户确认
    PENDING_CONFIRMATION --> REJECTED : 用户拒绝 / 被新草案替代
    ACTIVE --> SUPERSEDED : 新 ACTIVE 生效
    ACTIVE --> ARCHIVED : Stream 归档
    REJECTED --> [*]
    SUPERSEDED --> [*]
    ARCHIVED --> [*]
```

说明：

- `DRAFT` 状态保留给未来「编辑器自动保存」，v1.0 不使用。
- `ACTIVE` 同一 Stream 至多一个（部分唯一索引）。
- `SUPERSEDED` 与 `ARCHIVED` 仅用于历史查询，不进入 Agent 上下文。
- 版本号在写入时分配，允许因拒绝产生空号；顺序比连续性重要。

### 4.1 生效时间

- 确认时写入 `effective_from = now()`；旧版本 `effective_until = now()`。
- v1.0 不支持「未来生效」或「定时生效」；需要时由用户到点再确认。
- `confirmed_at` 与 `effective_from` 在 v1.0 相同；分开保留是为了未来支持预约生效。

---

## 5. AI 辅助：解析与润色

### 5.1 触发方式

只在 Thesis 编辑器中由用户显式点击触发。**对话窗口不触发解析/润色，也不保存结果。**

- **AI 润色**（`THESIS_POLISH`）：先改善表达，不改事实；
- **AI 帮我整理**（`THESIS_PARSE`）：把文字变成结构化字段；
- 两者都只返回建议，不落库；用户编辑/确认后才生成版本。

润色流程：

```text
用户原文（编辑器 textarea）
  → 点击「AI 润色」
  → AgentRun(task=THESIS_POLISH) 固定原文 + 当前 ACTIVE 版本
  → 返回 polished_text + change_notes + warnings
  → 编辑器并排 diff；用户可「采用润色 / 保留原文 / 手动编辑」
  → final_text 确定
  → 可选：点击「AI 帮我整理」生成结构化草案
  → 提交：按 MATERIAL/MINOR 规则生成版本
```

解析流程：

```text
用户输入 natural language（编辑器 textarea）
  → 点击「AI 帮我整理」
  → AgentRun(task=THESIS_PARSE) 固定当前 ACTIVE 版本 + 原文（或 final_text）
  → 返回结构化草案 + unparsed + clarifying_questions
  → 编辑器回填字段（用户可改）
  → 用户提交：按 MATERIAL/MINOR 规则生成版本
```

### 5.2 解析输出契约

```json
{
  "draft": { "...": "符合第 2 节 Schema" },
  "unparsed": [
    {"text": "如果宏观流动性收紧，我可能会重新考虑", "reason": "缺少可结构化字段"}
  ],
  "clarifying_questions": [
    "你说的「短期」大概是指几天、几周还是几个月？"
  ],
  "warnings": [
    "你提到 65,000 的回调目标，但没有说明该情景失效的条件"
  ]
}
```

规则：

- `draft` 必须通过 JSON Schema 校验；失败则整次解析失败，保留原文。
- `unparsed` 必须保留原文片段，不能丢弃用户表达。
- `clarifying_questions` 最多 3 条；只清理原文中的真实歧义（指代、术语、明显矛盾），不预测未来、不补全未提供的参数；只是建议，不阻塞保存，也不自动改用户的原文/JSON。
- 解析不得给出买卖建议，不得引入用户未提过的新策略。
- 解析不得把「我希望」写成「我已经」；不得把 AI 推断写入 `constraints`。
- 若用户原话包含明显矛盾（如「短期看涨」但目标价低于现价），写入 `warnings`，不擅自修正。

### 5.3 解析失败与降级

| 情况 | 行为 |
|---|---|
| 模型超时 | 30s 超时，提示重试；原文不丢 |
| JSON 不合法 | 重试 1 次；仍失败则提示「暂时无法整理，可直接手填」 |
| 结构化字段为空 | 合法：观察型论点，允许提交 |
| 用户取消 | 丢弃草案；不产生版本、不产生 AgentRun 之外的写入 |

### 5.4 AI 润色（THESIS_POLISH）

**目标**：让用户的原话更清晰、更有条理、更易读，但**不改变用户的意思**。

允许：

- 调整语序、断句、段落；
- 去掉重复、口语填充词；
- 把含糊表达改清楚（在不新增信息的前提下）；
- 统一术语与第一人称口吻；
- 保持中文（或原文语言）。

禁止：

- 新增/删除数字、价格、百分比、日期；
- 改变方向判断（看涨/看跌/中性）、时间周期、加减仓意图；
- 新增目标价、止损、风险预算、约束、事实或新闻；
- 把用户观点改写成投资建议；
- 添加原文没有的确定性（如「可能」改成「一定」）；
- 使用夸张、催促、情绪化措辞。

输出契约：

```json
{
  "polished_text": "我认为 BTC 短期可能转空，预计回调至 65,000 附近；但中长期依然看涨，回调可能是下一轮上涨的机会。目前不希望因短期下跌而完全离场，也不使用杠杆。",
  "change_notes": [
    {
      "kind": "CLARITY",
      "before": "短期可能转空，可能回调到 65000 附近",
      "after": "短期可能转空，预计回调至 65,000 附近",
      "reason": "统一数字格式与句式"
    }
  ],
  "warnings": [
    "原文中的「不使用杠杆」已保留，未新增其他约束"
  ],
  "meaning_preserved": true
}
```

校验：

| 检查 | 规则 | 失败处理 |
|---|---|---|
| 数字集合 | 润色前后的数字 token 集合必须一致 | warning + 高亮，需用户确认 |
| 方向词 | 看涨/看跌/中性/加仓/减仓/清仓/持有不得翻转 | 阻止自动采用，要求重新润色 |
| 否定词 | 「不/没有/避免/不希望」数量与语义不得丢失 | warning + 高亮 |
| 长度 | 0.5x–2x 原文；超限 warning | 不阻断 |
| 语言 | 与原文一致 | 不一致则失败 |
| 建议化 | 不得出现「建议你买/卖」等新增指令 | 失败，重新生成 |

**润色不自动保存**：`polished_text` 只存在于响应与 UI；用户点击「采用润色」或手动编辑后，才写入提交请求的 `final_text`。

### 5.5 编辑窗口流程

独立页面（不是聊天面板）：`/streams/{id}/thesis/edit`。

```text
┌─────────────────────────────────────────────────────┐
│ Thesis · BTC 长期配置            v3 ACTIVE · 历史   │
├──────────────────────────┬──────────────────────────┤
│ 你的原文（可编辑）        │ AI 润色建议（只读/diff）  │
│ 我认为 BTC 短期可能转空…  │ 我认为 BTC 短期可能转空…  │
│                          │ [采用润色] [保留原文]     │
├──────────────────────────┴──────────────────────────┤
│ 结构化字段：方向 / 周期 / 情景 / 风险 / 约束          │
│ [AI 帮我整理]                                        │
├─────────────────────────────────────────────────────┤
│ 变更摘要 + diff（MATERIAL 时高亮）                    │
│ [保存草稿] [确认生效]                                 │
└─────────────────────────────────────────────────────┘
```

规则：

- `original_text`：用户进入编辑器时的原始输入；手动编辑会更新原文（仍属于用户输入）。
- `final_text`：用户最终确认的正文；可采用润色，也可手动编辑；为空时回退 `original_text`。
- 「AI 帮我整理」使用 `final_text or original_text` 作为输入。
- 提交前展示结构化 diff；MATERIAL 必须点击「确认生效」，MINOR 提交即生效。
- 历史版本同时展示「原文」与「确认正文」，并标注是否使用过 AI 润色/整理。
- 对话窗口不能打开这个流程，也不能代替用户点击确认。

数据模型：

| 字段 | 含义 |
|---|---|
| `original_text` | 用户原始输入，永不覆盖 |
| `final_text` | 用户确认正文（可润色/编辑）；空则回退 |
| `polish_agent_run_id` | 润色 Run，可空 |
| `source_agent_run_id` | 结构化 Run，可空 |

---

## 6. Diff 与历史

### 6.1 Diff 结构

`diff_from_previous` 保存机器可读的变更：

```json
[
  {
    "op": "replace",
    "path": "/market_outlook/short_term",
    "before": "NEUTRAL",
    "after": "BEARISH",
    "classification": "MATERIAL"
  },
  {
    "op": "add",
    "path": "/scenarios/-",
    "before": null,
    "after": {
      "direction": "DOWN",
      "target_price": "65000",
      "time_horizon": "SHORT_TERM"
    },
    "classification": "MATERIAL"
  },
  {
    "op": "replace",
    "path": "/notes",
    "before": "关注 ETF 流入",
    "after": "关注 ETF 流入与宏观流动性",
    "classification": "MINOR"
  }
]
```

### 6.2 历史视图

- 文本层面的润色差异单独展示（`original_text` → `final_text`），不写入 `diff_from_previous`；后者只记录结构化字段变化。
- 版本列表：版本号、状态、来源、`change_class`、生效时间、变更摘要、是否使用过 AI 润色/整理。
- 版本详情：原文、确认正文（`final_text`）、结构化内容、diff、`source_agent_run_id`、`polish_agent_run_id`、确认时间。
- 任意两版本对比：并排 diff；默认对比上一版。
- 旧版本不能删除；可以归档 Stream。

---

## 7. 与对话、监控的关系

### 7.1 对话

- 对话**只读** Thesis：`get_investment_thesis` 只返回 ACTIVE 版本（优先 `final_text`）；`get_thesis_history` 返回历史。
- 用户说「帮我改成看空」→ 对话不能写，只能解释并指出编辑器路径。
- 用户说「帮我润色一下」→ 对话不能触发润色；指向独立编辑器的「AI 润色」。
- 对话可以引用「你当前 v3 说……」，但不能说「我已经帮你改成 v4」。
- 对话中的观点变化不会自动成为版本；这是 D13/D14 的硬边界。

### 7.2 定时分析

- 每次 `MONITOR_ANALYSIS` 固定当次 ACTIVE 版本 ID；运行中 Thesis 变化不影响本次上下文。
- 若存在永续持仓，同时固定 derivative snapshot；`derivative_intent` 作为杠杆/保证金/做空权限的硬约束。
- 下一轮使用新版本（优先 `final_text`），并在 `changes_since_previous` 中解释版本差异。
- 没有 ACTIVE 版本（观察型）时，Agent 只能基于行情与持仓分析，明确声明「没有正式论点」。

### 7.3 Proposal（v1.2+）

- v1.0 不产生 Proposal；AI 草案在编辑器中回填，确认后直接生成版本。
- 未来渠道写操作时，Proposal 才承载「待确认的 Thesis 变更」；确认后仍走本节的版本写入规则。

---

## 8. 校验规则

### 8.1 Schema 校验

- `schema_version` 必填且受支持。
- 金额/价格字符串必须能解析为 `Decimal`，且 `> 0`。
- 百分比字段 `0 <= x <= 100`。
- `scenarios[].id` 在数组内唯一。
- `target_currency` 默认等于 Instrument 的 `quote_currency`；不一致时 warning。
- `max_position_pct` 与 `preferred_position_pct` 不强制大小关系，但若 preferred > max 给 warning。
- `derivative_intent.max_leverage` 在 `0.1–125`；`max_margin_usd >= 0`；`min_liquidation_buffer_pct` 在 `0–100`。
- `derivative_intent.allow_perpetual=false` 但存在永续持仓 → warning「观点禁止永续，但账本里有持仓」。

### 8.2 语义警告（不阻断保存）

| 情况 | 处理 |
|---|---|
| 短期 `BEARISH` 但目标价高于现价 | warning：「方向与目标价可能不一致」 |
| `DOWN` 情景目标价高于现价 | warning |
| `UP` 情景目标价低于现价 | warning |
| 有 `scenarios` 但没有 `invalidation` | warning：「建议补充失效条件」 |
| `risk` 全空 | warning：「未设置风险预算，建议补充」 |
| `constraints` 含「不使用杠杆」但 `position_intent` 无对应 | 不处理（自然语言约束由 Agent 解释） |

警告只展示给用户，不自动修改字段。

### 8.3 原文与润色文本校验

- `original_text` 非空，长度 1–20,000 字符。
- `final_text` 可空；非空时长度 1–20,000 字符，且必须与 `original_text` 同时保存。
- 提交时保存原文快照；后续编辑生成新版本，不 UPDATE 旧原文。
- 原文/润色文本中的 HTML/脚本按纯文本处理；前端转义渲染。
- AI 润色额外校验：数字集合、方向词、否定词、语言一致性；失败时给出 warning 或要求重新润色。

---

## 9. API 轮廓

详细见 `05-api.md`。

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/streams/{id}/thesis` | 当前 ACTIVE 版本 + 结构化内容 |
| GET | `/streams/{id}/thesis/versions` | 版本列表（分页） |
| GET | `/thesis/versions/{id}` | 版本详情 |
| GET | `/thesis/versions/{id}/diff?against={other}` | 版本对比 |
| POST | `/streams/{id}/thesis/parse` | AI 整理，返回草案；不落库 |
| POST | `/streams/{id}/thesis/polish` | AI 润色，返回建议；不落库 |
| POST | `/streams/{id}/thesis/versions` | 提交新版本（MATERIAL → PENDING） |
| POST | `/thesis/versions/{id}/confirm` | 确认 MATERIAL 版本 |
| POST | `/thesis/versions/{id}/reject` | 拒绝 |
| PATCH | `/thesis/versions/{id}` | 编辑尚未确认的版本（仅 PENDING） |

---

## 10. 示例：从原话到版本

### 10.1 用户输入

> 我认为 BTC 短期可能转空，预计回调至 65,000 附近；但中长期依然看涨，认为回调可能是下一轮上涨的机会。目前不希望因为短期下跌就完全离场，也不使用杠杆。

### 10.2 解析结果

```json
{
  "schema_version": "1.0",
  "thesis_statement": "短期可能回调至 65,000，中长期看涨；不因短期下跌清仓，不使用杠杆",
  "time_horizon": {
    "short_term": "WEEKS",
    "medium_term": "MONTHS",
    "long_term": "YEARS"
  },
  "market_outlook": {
    "short_term": "BEARISH",
    "medium_term": "NEUTRAL",
    "long_term": "BULLISH"
  },
  "scenarios": [
    {
      "id": "S1",
      "direction": "DOWN",
      "target_price": "65000",
      "target_currency": "USDT",
      "time_horizon": "SHORT_TERM",
      "status": "USER_EXPECTATION",
      "conditions": [],
      "invalidation": null
    }
  ],
  "constraints": [
    "不希望仅因短期下跌而完全离场",
    "不使用杠杆"
  ],
  "risk": {},
  "position_intent": {},
  "key_levels": {},
  "open_questions": [],
  "notes": null
}
```

### 10.3 版本记录

- `source = AGENT`（结构化由 AI 整理），`source_agent_run_id` 指向解析 Run；
- 若使用过润色：`final_text` 保存确认正文，`polish_agent_run_id` 指向润色 Run；`original_text` 仍是用户最初输入；
- `change_class = MATERIAL`（新增下行情景、方向、约束）；纯文字润色不改变结构化内容时为 `MINOR`；
- 首次版本：`version = 1`，`status = PENDING_CONFIRMATION`；
- 用户确认后 `ACTIVE`，`confirmed_at = now()`；
- 下一轮监控固定 `thesis_version_id = v1`。

---

## 11. 开放问题

| # | 问题 | 当前默认 |
|---|---|---|
| T1 | `key_levels` 是否应算 MATERIAL？ | v1 算 MINOR；若用户反对再改 |
| T2 | 是否允许未来生效时间？ | v1 不允许 |
| T3 | 是否允许多个 PENDING 草案？ | 不允许，只保留一个 |
| T4 | AI 解析的 `field_confidence` 是否展示？ | v1 不展示，只展示 warnings |
| T5 | 观察型 Stream 是否需要强制填写 `thesis_statement`？ | 不需要，允许只有原文 |
| T6 | 润色是否允许调整段落结构？ | 允许；以不改变语义为前提 |
| T7 | `final_text` 是否可能为空？ | 可以；Agent 回退到 `original_text` |