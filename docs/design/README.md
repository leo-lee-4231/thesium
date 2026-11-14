# Thesium 设计文档

> 设计原则一句话：**对话是思考空间，Thesis 是承诺；对话只读，正式变更由用户显式提交。**

本目录记录 Thesium v1 的产品边界、领域模型与工程契约。文档先于代码，口径确认后再进入 P0。

## 阅读顺序

| # | 文档 | 内容 | 状态 |
|---|---|---|---|
| 00 | [架构决策记录](00-decisions.md) | D1–D15，含对话/渠道/只读边界 | 已确认 |
| 01 | [领域模型](01-domain-model.md) | 限界上下文、聚合不变量、ER 图、核心表与索引 | 草案 |
| 02 | [Investment Thesis](02-thesis.md) | 状态机、JSON Schema、分级确认规则 | 草案 |
| 03 | [Agent Runtime](03-agent-runtime.md) | Prompt 分层、Tool Registry、Run 生命周期、对话装配 | 草案 |
| 04 | [决策与通知](04-decisions-notifications.md) | Decision Schema、通知优先级/冷却/去重 | 草案 |
| 05 | [REST API](05-api.md) | Web、对话、渠道、确认接口草案 | 草案 |
| 06 | [路线图](06-roadmap.md) | P0–P7 任务拆分与验收场景 | 草案 |
| 07 | [对话与多渠道](07-conversation-and-channels.md) | 对话域、渠道适配器、飞书接入、安全与语气 | 草案 |

## 当前结论（TL;DR）

1. **v1.0 = BTC 现货核心闭环 + Web 只读对话**；飞书渠道 v1.1。
2. 对话复用同一个 Agent Runtime，不是第二个 Agent；Web / 飞书都是薄客户端。
3. **对话只读**：可查行情/指标/持仓/Thesis/历史决策，可给情景化操作框架与情绪支持；不能创建 Proposal、不能改 Thesis 或持仓。
4. 正式变更只发生在 Web 编辑器/表单：Thesis 手动编辑或「AI 帮我整理」生成草案，用户确认后生效；持仓由用户录入成交或修正。
5. 渠道先做 **飞书自建应用**（官方 API、WebSocket 长连接、手机推送、无需公网 IP）；**个人微信不做**。
6. 单租户没有登录，IM 机器人按高敏资产对待：**配对码 + 白名单 + 可撤销绑定**；渠道只读。

## 尚未确认

- 飞书是否默认推送 HIGH/URGENT 决策（邮件 + IM），以及只推摘要（不影响领域模型，v1.1 前决定）。