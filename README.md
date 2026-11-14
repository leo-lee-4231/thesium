# Thesium

> **Your thesis, kept honest.** · 让你的投资论点，始终经得起检验。

An auditable, self-hosted personal investment agent: it remembers what you actually hold and what you actually said, and gives you a receipt every time the story changes.

一个可审计、自托管的个人投资 Agent：记住你真实持有什么、原话怎么想；每次改口，都给收据。

---

## 它是什么

- 围绕 **Investment Stream**（首版：BTC 现货）持续跟踪行情与持仓；
- 用 **Investment Thesis** 版本化保存你的投资目标、观点、目标价与约束；
- 定时调用你配置的 OpenAI 兼容模型，输出**结构化、可追溯**的分析与建议；
- 支持 **Web 对话**，并可延伸到 **飞书机器人**，外出时也能问一句「我的论点还成立吗」；
- 所有建议都绑定当时的 Thesis 版本、持仓快照和行情时间戳，事后可以回放。

## 它不是什么

- 不是自动交易机器人，不连接交易所下单；
- 不是量化回测平台，不需要你写指标规则；
- 不是通用聊天助手，对话永远锚定在你的投资流上；
- 不是「AI 替你改观点」：AI 只能提议，正式变更必须你确认。

## 核心原则

1. **三分**：客观市场事实 / 用户真实持仓 / 用户正式观点 / AI 推断，互不覆盖。
2. **只追加**：Thesis、持仓事件、决策、对话消息都是历史，不静默改写。
3. **可追溯**：每次分析固定证件版本、持仓快照、行情时间与模型。
4. **对话是思考空间，Thesis 是承诺**：聊天不能直接改 Thesis，只能生成 Proposal，确认后生效。
5. **渠道是传输层**：Web、飞书共用同一个 Agent Runtime，不出现两套说法。
6. **数据过期就承认**：`STALE` / `UNKNOWN` 不允许伪装成实时。

## 架构（设计阶段）

```text
Web (Vue 3)          Feishu Bot          future: WeCom / MCP
     |                    |
     +--------+-----------+
              |
        FastAPI API / Channel Gateway
              |
     Application Services + Agent Runtime (Tool Registry)
              |
        Repositories / PostgreSQL
              |
   Binance Market Provider · OpenAI-compatible LLM · Email
              |
     Scheduler → Worker → Agent Run → Decision → Notification
```

- **Headless 核心 + 薄表面**：业务规则只在应用服务与 Runtime 中。
- **单租户**，保留 `user_id`，首版不做注册登录。
- **PostgreSQL 任务表 + 独立 Worker**，不引入 Celery/Redis。
- 金额与价格：`NUMERIC` / `Decimal`，禁止浮点。

## 技术栈

Python 3.12 · FastAPI · SQLAlchemy 2.0 async · Pydantic v2 · Alembic · PostgreSQL 16 · Vue 3 + TypeScript + Vite + ECharts · Docker Compose · pytest · GitHub Actions

## 文档

| 文档 | 内容 |
|---|---|
| [设计文档索引](docs/design/README.md) | 阅读顺序与当前结论 |
| [00 · 架构决策](docs/design/00-decisions.md) | D1–D14，含对话/渠道新增提案 |
| [01 · 领域模型](docs/design/01-domain-model.md) | 聚合、不变量、ER 图、表与索引 |
| [07 · 对话与多渠道](docs/design/07-conversation-and-channels.md) | 对话域、飞书接入、安全、验收 |

02–06（Thesis、Runtime、决策通知、API、路线图）待口径确认后补齐。

## 状态

**设计阶段，尚不可运行。** 下一步：确认 MVP 范围与渠道选择 → 补全设计文档 → P0 骨架（Docker Compose + FastAPI + Postgres + Web 壳）。

## 许可证

[AGPL-3.0](LICENSE)。