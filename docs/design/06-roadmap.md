# 06 · 路线图与工程计划

> 状态：草案 v0.1
> 范围：v1.0 = BTC 现货核心闭环 + Web 只读对话；v1.1 = 飞书只读渠道；v1.2+ = 增强。
> 预估口径：人日为乐观量级（有 AI 辅助、熟悉技术栈），实际取决于投入时间；业余每周 15–20 小时大约对应 8–10 周，全职约 5–6 周。以里程碑验收为准，不承诺日历日期。

---

## 1. 原则

1. **先闭环，再加面**：Thesis 版本、持仓快照、Decision、通知先跑通，对话复用同一 Runtime。
2. **每一步可演示**：每个 P 阶段结束都有可运行的结果，不做「最后一次性集成」。
3. **迁移先行**：数据库结构变更必须带 Alembic migration 和回滚测试。
4. **不引入不必要的中间件**：v1 用 PostgreSQL 任务表 + Worker；不引入 Redis/Celery/Kafka。
5. **安全默认关闭**：单租户不等于无边界；默认只绑本地，暴露必须加 token。

---

## 2. 里程碑

| 里程碑 | 内容 | 人日 | 累计 |
|---|---|---:|---:|
| M0 | 骨架可启动：Docker Compose、FastAPI、Postgres、Web 壳、CI | 2 | 2 |
| M1 | 行情 + Stream：OKX SPOT/SWAP、K 线、指标、产品卡 | 5 | 7 |
| M2 | 持仓：现货 + USDT 永续、快照、风险、录入表单 | 6 | 13 |
| M3 | Thesis：Schema、解析、润色、版本、分级确认、diff | 6 | 19 |
| M4 | 监控：Runtime、工具、Decision（现货+合约）、Scheduler、邮件 | 8 | 27 |
| M5 | Web 对话：Conversation、SSE、只读工具、语气 | 6 | 33 |
| M6 | Dashboard 与可追溯性、验收、发布 v1.0 | 3 | 36 |
| M7 | 飞书只读渠道 + 推送 | 5 | 41 |
| M8 | 硬化：备份、安全、文档、v1.1 发布 | 2 | 43 |

> M0–M6 是 v1.0；M7–M8 是 v1.1。M4 与 M5 的顺序可交换，但对话依赖 Runtime，不能早于 M4。

---

## 3. P0 · 骨架

**目标**：`docker compose up` 后能打开 Web、访问 `/health`、连上 Postgres，CI 绿。

任务：

- 目录结构：`backend/`、`frontend/`、`deploy/`、`docs/`。
- Backend：Python 3.12 + uv；FastAPI app factory；Pydantic Settings；结构化日志；统一错误处理。
- DB：SQLAlchemy 2.0 async + asyncpg；Alembic 初始化；`users`/`assets`/`instruments` seed。
- 健康检查：`/health`、`/ready`。
- Worker 进程骨架（空循环 + 优雅退出）。
- Frontend：Vue 3 + TS + Vite + Router + Pinia；空 Dashboard；API client。
- Docker Compose：postgres、api、worker、web；卷、健康检查、依赖顺序。
- CI：ruff、mypy、pytest、eslint、vue-tsc、vite build、docker build。
- `Makefile`：`make dev`、`make test`、`make lint`、`make migrate`。

验收：

- 全新机器 `docker compose up -d` → `http://localhost:8080` 显示壳；`/health` 200。
- `alembic upgrade head` 与 `downgrade base` 均可执行。
- CI 在 PR 上通过。

---

## 4. P1 · 行情与产品

**目标**：创建 BTC 投资产品，看到 OKX 现货报价、SWAP 观察数据、K 线和基础指标。

任务：

- Market Provider 接口；**OKXProvider**（ticker、klines、mark price、funding rate、open interest）；超时、重试、限频、错误映射。
- Instruments：`BTC-USDT`（SPOT）、`BTC-USDT-SWAP`（SWAP）；Provider 契约测试覆盖两类。
- K 线采集：每小时增量 + 首次回填 30 天；`market_candles` 唯一键幂等；日线用 OKX `1Dutc`，统一到 UTC。
- 指标计算：EMA20、RSI14、MACD、波动率；多周期（1h/4h/1d）；纯函数 + 单测。
- 行情快照：`market_snapshots` + `staleness`（FRESH/STALE/UNKNOWN）；衍生品观察单独字段。
- 产品 CRUD；首版限制一个 ACTIVE；Web 产品卡 + 详情页 + K 线图（ECharts）。
- 资产目录：`GET /assets` 返回资产与 SPOT/SWAP 标的。

验收：

- OKX 不可用时，页面显示 `STALE/UNKNOWN`，不显示假实时。
- K 线重复采集不产生重复行；日线边界与 UTC 聚合结果一致。
- 指标数值与独立计算脚本一致（golden test）。
- 产品卡可点击进入详情；现货与 SWAP 数据分开展示。

---

## 5. P2 · 持仓（现货 + USDT 永续）

**目标**：录入现货成交与永续持仓/事件，得到正确的风险快照。

任务：

- 现货：Position Event（BUY/SELL/CORRECTION/OPENING）；加权平均成本；手续费；事务与快照。
- 永续：`derivative_positions` / events / snapshots；OPEN/INCREASE/REDUCE/CLOSE/ADJUST_MARGIN/FUNDING/CORRECTION；单向持仓。
- 永续计算：notional、uPnL、ROE、保证金占用、距用户清算价百分比、风险预算占用。
- **清算价只接受用户输入**；不估算；为空时风险字段为 null。
- Web：现货/永续两个 Tab，表单、事件时间线、风险卡片；数量单位提示（基础资产 vs OKX 张数）。
- 幂等：`Idempotency-Key`；并发提交保护；方向冲突返回 409。

验收：

- 连续买卖后现货数量、成本、已实现盈亏与手工计算一致。
- 永续多/空 uPnL、ROE、距清算价与手工计算一致；方向冲突被拒绝。
- 修正后旧事件仍可查，快照不可变。
- 未填清算价时不显示假数字。

---

## 6. P3 · Investment Thesis

**目标**：自然语言 → 结构化草案 → diff → 确认 → 版本历史；支持 AI 润色。

任务：

- Thesis JSON Schema + Pydantic 校验 + 语义 warning。
- `THESIS_PARSE` Prompt + 输出契约（draft/unparsed/clarifying/warnings）。
- `THESIS_POLISH` Prompt + 输出契约（polished_text/change_notes/warnings）；数字/方向/否定校验。
- 版本写入、MATERIAL/MINOR 判定、PENDING/ACTIVE/SUPERSEDED 状态机。
- 部分唯一索引（一个 ACTIVE、一个 PENDING）。
- diff 生成与存储；版本对比 API。
- Web：独立编辑页、AI 润色 diff、AI 整理、结构化字段、确认页、历史时间线。
- 双文本：`original_text` / `final_text` / `polish_agent_run_id`。
- 审计：`source_agent_run_id`、`polish_agent_run_id`、`audit_logs`。

验收：

- 原文包含「短期看空到 65,000，中长期看涨」→ 结构化为 BEARISH/BULLISH + DOWN 场景。
- 点击「AI 润色」→ 文字更清晰，数字/方向/约束不变；用户可采用、拒绝或手动编辑。
- MATERIAL 修改必须确认；MINOR 直接生效。
- 旧版本可查；确认后下一轮分析使用 `final_text`。
- AI 解析/润色失败不丢原文。

---

## 7. P4 · Agent Runtime 与监控

**目标**：定时分析跑通，生成可追溯 Decision，重要变化发邮件。

任务：

- LLM Provider：OpenAI 兼容客户端、工具调用、流式、超时/重试、连接测试。
- Tool Registry：Market/Portfolio/Thesis/Decision 读取工具；越权与参数校验。
- ContextBuilder：监控上下文；固定 Thesis/现货快照/永续快照/Market 版本。
- Prompt：system/monitor v1；输出 Decision Schema（含 `derivative_recommendation`）。
- OutputValidator：Schema + 业务规则 + 合约动作方向校验 + 重试。
- `agent_runs` / `decisions` 持久化；1:1 约束。
- Scheduler：APScheduler 或 Worker 内 cron；`jobs` 表 + `FOR UPDATE SKIP LOCKED`。
- 通知策略：优先级、类别跃迁、alignment、冷却、去重；邮件发送 + 重试。
- Web：Decision 时间线、Run 详情、通知记录。
- Fake LLM 集成测试（含非法 JSON、限流、超时）。

验收：

- 定时任务按 Stream 间隔运行；重复 tick 不产生重复 Decision。
- Decision 绑定正确的 Thesis 版本、持仓快照、行情时间戳。
- 普通 WAIT 不发邮件；HOLD→SELL 发一封；4h 内不重复。
- 模型输出不合法时 Run FAILED，不写 Decision、不发通知。
- 有永续持仓时缺少 `derivative_recommendation` → 校验失败；动作与方向不匹配 → 拒绝。

---

## 8. P5 · Web 对话

**目标**：在 Stream 内连续提问，得到有依据、只读、带来源的回答。

任务：

- `conversations` / `conversation_messages`；seq 分配；幂等。
- ConversationService：创建/取会话、落用户消息、调用 Runtime、落助手消息。
- ContextBuilder（对话）：Stream brief + Thesis + 现货/永续持仓 + 衍生品观察 + 最近 Decision + 摘要 + 最近 12 条。
- 只读工具集：行情、指标、衍生品观察、Thesis、现货/永续持仓、风险、Decision、`simulate_position_change`、`simulate_derivative_change`。
- 只读约束：无写工具；输出后置检查（「已帮你改」拦截）。
- SSE：meta/status/tool/delta/done/error；断线补齐。
- 滚动摘要（阈值 + 失败降级）。
- Web：Ask 面板、快捷问题、来源折叠、错误/STALE 状态。
- 语气评估集：问价、论点检视、改观点请求、亏损焦虑、要求下单、数据过期。

验收：

- 问价必须调用工具并带时间戳。
- 要求改 Thesis/记成交 → 明确拒绝代写并指路；数据库无变更。
- 亏损焦虑 → 不催促、不保证、给 if-then 选项。
- 任意回答可打开 Run 详情。
- 问「合约现在风险大吗」→ 引用用户清算价与距清算价距离，不编造交易所清算价。

---

## 9. P6 · Dashboard、可追溯与 v1.0 验收

**目标**：一屏看清「行情 / 持仓 / 论点 / 最新建议」，并能回放。

任务：

- Stream Overview：行情、持仓、风险、ACTIVE Thesis、最新 Decision。
- Decision 时间线 + 前后变化 + Run 详情（工具、版本、token、耗时）。
- Thesis 历史与 diff；持仓事件时间线。
- 通知中心；设置页（Provider、邮箱、通知偏好）。
- 空状态、错误状态、加载状态；移动端响应式 + PWA。
- 验收场景 A–E（见原文档）+ 对话场景。
- 文档：部署、备份、恢复、常见问题。

验收：

- 新用户 15 分钟内完成配置 → 看到第一条分析。
- 从任意 Decision 能回答「当时用的哪版观点/持仓/行情/模型」。
- 所有金额计算用 Decimal；DB 为 NUMERIC。

---

## 10. P7 · 飞书只读渠道（v1.1）

**目标**：绑定后可在飞书问同样的问题，接收重要决策摘要。

任务：

- `ChannelAdapter` 接口 + `InboundMessage`/`OutboundMessage`；模拟器。
- 飞书自建应用：长连接、事件订阅、消息回复；权限与错误处理。
- 配对码：生成、hash、TTL、一次性、白名单、撤销。
- 渠道入站：幂等、异步 ACK、单飞、限流。
- 只读问答：复用 ConversationService，不新增业务逻辑。
- `/why`：返回最近回答的 Run 摘要。
- 通知推送：HIGH/URGENT 摘要 + Web 链接；可关。
- 投递记录与重试；未绑定拒绝。
- 部署文档：飞书应用配置步骤。

验收：

- 未绑定发送被拒；配对成功后可用；撤销后立即失效。
- 重复事件只回一次；飞书 ACK < 3s，回答异步到达。
- 飞书里要求改 Thesis → 拒绝并引导 Web；数据库无变更。
- 重要决策摘要推送，不含完整持仓。

---

## 11. 工程结构

```text
thesium/
├── backend/
│   ├── pyproject.toml
│   ├── alembic.ini
│   ├── alembic/
│   │   └── versions/
│   ├── app/
│   │   ├── main.py
│   │   ├── core/            # config, logging, security, errors
│   │   ├── api/v1/          # routers
│   │   ├── domain/          # entities, value objects, policies
│   │   ├── application/     # services (thesis, portfolio, conversation, notification)
│   │   ├── infrastructure/  # db, market, llm, email, channels
│   │   ├── agent/           # runtime, prompts, tools, validators
│   │   └── workers/         # scheduler, job runner
│   └── tests/
├── frontend/
│   ├── package.json
│   ├── src/
│   │   ├── api/
│   │   ├── components/
│   │   ├── views/
│   │   ├── stores/
│   │   └── router/
│   └── tests/
├── deploy/
│   ├── docker-compose.yml
│   ├── Dockerfile.api
│   ├── Dockerfile.web
│   └── nginx.conf
├── docs/
│   └── design/
└── Makefile
```

原则：

- `domain/` 不依赖 FastAPI/SQLAlchemy/LLM SDK；
- `application/` 编排领域服务与仓储接口；
- `infrastructure/` 实现仓储、Provider、邮件、飞书；
- `agent/tools/` 只调用 application service，不碰 DB；
- `api/` 只做参数校验与响应映射。

---

## 12. 测试策略

| 层级 | 内容 | 工具 |
|---|---|---|
| 单元 | 指标计算、成本/盈亏、diff、策略规则 | pytest |
| 集成 | Repository、迁移、API、SSE | pytest + httpx + testcontainers/本地 PG |
| Agent | Fake LLM 的 tool loop、Schema 校验、失败重试 | pytest + respx |
| 对话安全 | 只读拦截、情绪支持、数据过期 | pytest + 评估集 |
| 前端 | 组件、表单、diff 视图 | Vitest + Vue Test Utils |
| E2E | 首次配置→分析→对话→改 Thesis | Playwright（可选，M6） |

Fake LLM：

- 本地 HTTP server 返回固定 chat completions / tool_calls / SSE；
- 可配置限流、超时、非法 JSON；
- 测试不依赖真实 API Key。

---

## 13. CI / 质量门禁

```bash
# backend
ruff check .
ruff format --check .
mypy app
pytest -q

# frontend
pnpm lint
pnpm typecheck
pnpm test --run
pnpm build

# 迁移
alembic upgrade head
alembic downgrade -1
alembic upgrade head
```

- PR 必须绿；main 保护。
- 依赖漏洞扫描（pip-audit / pnpm audit）每周。
- Docker 镜像构建通过。

---

## 14. 完成定义（DoD）

一个任务完成必须满足：

1. 代码 + 测试 + 迁移（如涉及）；
2. 错误路径有处理，不吞异常；
3. 日志无密钥/完整消息；
4. API 变更同步 OpenAPI 与前端类型；
5. 文档/注释更新；
6. 在 Docker Compose 下手动验证一次；
7. 不引入新的未使用依赖。

---

## 15. 风险与对策

| 风险 | 影响 | 对策 |
|---|---|---|
| 对话范围膨胀成通用助手 | 工期失控、定位模糊 | 只读 + Stream 锚定 + 非目标清单；新能力进 backlog |
| Provider 不支持工具调用 | 监控无法可靠运行 | 连接测试强制校验 tools；不支持则明确报错 |
| Binance 地区限制/限频 | 行情不可用 | 错误映射 + STALE；预留第二个 Provider 接口 |
| Worker/Scheduler 重复执行 | 重复 Decision/通知 | jobs 去重 + 唯一约束 + 幂等键 |
| 金额浮点误差 | 账目错误 | NUMERIC + Decimal + 字符串 JSON；禁止 float |
| 单租户无登录被公网访问 | 持仓泄露 | 默认本地绑定；非本地必须 token；推荐隧道 |
| Thesis 版本并发提交 | 覆盖/混淆 | 一个 PENDING、base_version 校验、409 |
| 飞书长连接不稳定 | 消息丢失 | 事件幂等 + 重连 + 投递记录；Web 留底 |
| 业余时间不足 | 延期 | 按里程碑交付；M4 后可先自用，再补 UI |

---

## 16. 第一周建议

1. 完成 P0 骨架，确保 `docker compose up` 可用。
2. 写第一个 Alembic migration（users/assets/instruments/streams）。
3. 打通 `/health`、`/ready`、前端壳、CI。
4. 用 Fake Market Provider 写一个端到端冒烟测试。
5. 不急着接真实 Binance，先把边界与错误处理立住。

---

## 17. 与原交接文档的差异

- 原计划 v1.0 不含对话；现调整为 **v1.0 含 Web 只读对话**，飞书放 v1.1。
- 原计划对话可生成 Proposal；现明确 **对话只读**，正式变更走编辑器/表单。
- 增加 Thesis 编辑器内的 **AI 润色**（`THESIS_POLISH`）：只改表达、不改事实，原文与确认正文双保存。
- 增加语气与心理支持要求（D15），纳入 P5 验收。
- 行情源从 Binance 改为 **OKX 公共 API**（D18）；新增 **USDT 本位永续持仓/风险/建议**（D21/D22）与 SWAP 观察数据（D19）。
- 其余（单租户、BTC 首发资产、无新闻、分级确认、重要通知）不变。

---

## 18. 本地开发环境

| 项 | 约定 |
|---|---|
| Python | `pyenv virtualenv 3.12.8 thesium`；仓库 `.python-version` 指向它 |
| 后端依赖 | `python -m pip install -e "backend[dev]"`；国内可加 `-i https://mirrors.aliyun.com/pypi/simple/` |
| Node | nvm 读取 `.nvmrc`（24.21.0）；`npm install` |
| 前端构建 | `npm run typecheck && npm run build` |
| Docker Base Image | `PYTHON_IMAGE` / `NODE_IMAGE` / `NGINX_IMAGE` / `POSTGRES_IMAGE` 可配置；Docker Hub 不可达时在 `.env` 指向 DaoCloud 等镜像 |
| 数据库 | PostgreSQL 16，small profile（`shared_buffers=64MB`、`max_connections=20`、仅绑 `127.0.0.1:5432`）；`make backup` 做 `pg_dump` |
| 行情网络 | OKX 可能需要代理；启动 API 时设置 `HTTPS_PROXY` / `HTTP_PROXY`（本地例如 `http://127.0.0.1:7897`）；Docker 内用 `host.docker.internal` |
| 密钥/配置 | `.env` 不入库；只提交 `.env.example` |

说明：

- 清华 PyPI 源在不同网络可能返回 403；以实际可达的镜像为准，不把某个源写死进仓库。
- Docker 镜像同理：Dockerfile 使用 build args，不在 Dockerfile 里硬编码镜像站。
- 本地可直接用 pyenv + nvm 跑 API 与前端；Docker Compose 用于完整栈与部署验证。