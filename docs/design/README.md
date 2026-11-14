# Thesium 设计文档

> 设计原则一句话：**对话是思考空间，Thesis 是承诺；两者之间只能通过「已确认的 Proposal」流动。**

本目录记录 Thesium v1 的产品边界、领域模型与工程契约。文档先于代码，口径确认后再进入 P0。

## 阅读顺序

| # | 文档 | 内容 | 状态 |
|---|---|---|---|
| 00 | [架构决策记录](00-decisions.md) | D1–D8 沿用交接；D9–D14 为对话/渠道新增提案 | 待确认 |
| 01 | [领域模型](01-domain-model.md) | 限界上下文、聚合不变量、ER 图、核心表与索引 | 草案 |
| 02 | [Investment Thesis](02-thesis.md) | 状态机、JSON Schema、分级确认规则 | 待写 |
| 03 | [Agent Runtime](03-agent-runtime.md) | Prompt 分层、Tool Registry、Run 生命周期、对话装配 | 待写 |
| 04 | [决策与通知](04-decisions-notifications.md) | Decision Schema、通知优先级/冷却/去重 | 待写 |
| 05 | [REST API](05-api.md) | Web、对话、渠道、确认接口草案 | 待写 |
| 06 | [路线图](06-roadmap.md) | P0–P7 任务拆分与验收场景 | 待写 |
| 07 | [对话与多渠道](07-conversation-and-channels.md) | 对话域、渠道适配器、飞书接入、安全与可追溯 | 草案 |

## 当前结论（TL;DR）

1. 首版仍然先把 **BTC 现货 + Thesis 版本 + 持仓 + 定时分析 + 邮件** 的闭环跑通；对话复用同一个 Agent Runtime，不是第二个 Agent。
2. 架构形态是 **Headless 核心 + 薄表面**：Web、飞书、未来的 MCP 都只是入口，业务规则只存在一处。
3. 对话可以读行情/技术指标/持仓/Thesis/历史决策，但**不能直接改** Thesis 或持仓；只能生成 Proposal，由用户确认后生效。
4. 渠道先做 **飞书自建应用**（官方 API、WebSocket 长连接、手机推送、无需公网 IP）；**个人微信不做**（无官方 API，桥接违反 ToS 且有封号风险）。
5. 单租户没有登录，所以 IM 机器人是一条直达持仓与观点的通道：必须用 **配对码 + 白名单 + 一次性确认令牌** 当作凭证管理。

## 尚未确认

见 [00-decisions.md](00-decisions.md) 第 5 节。它们会影响 v1.0 / v1.1 的切分，但不影响领域模型。