# Thesium

> **Your thesis, kept honest.** · 让你的投资论点，始终经得起检验。

An auditable, self-hosted personal investment agent: it remembers what you actually hold and what you actually said, and gives you a receipt every time the story changes.

一个可审计、自托管的个人投资 Agent：记住你真实持有什么、原话怎么想；每次改口，都给收据。

---

## 它是什么

- 围绕 **Investment Product**（首版：BTC 现货 + USDT 永续）持续跟踪行情与持仓；
- 用 **Investment Thesis** 版本化保存你的投资目标、观点、目标价与约束；
- 定时调用你配置的 OpenAI 兼容模型，输出**结构化、可追溯**的分析与建议；
- 只把重要变化发邮件：类别跃迁、HIGH/URGENT、论点冲突、风险预算突破；普通 WAIT/HOLD 不打扰；
- 支持 **Web 只读对话**，可以问价格、趋势、论点一致性、情景与情绪支持；飞书渠道 v1.1 暂缓；
- 所有建议都绑定当时的 Thesis 版本、持仓快照和行情时间戳，事后可以回放。

## 它不是什么

- 不是自动交易机器人，不连接交易所下单；
- 不是量化回测平台，不需要你写指标规则；
- 不是通用聊天助手，对话永远锚定在你的投资流上；
- 不是「AI 替你改观点」：AI 可以润色表达、整理结构，但正式变更必须你确认。

## 核心原则

1. **三分**：客观市场事实 / 用户真实持仓 / 用户正式观点 / AI 推断，互不覆盖。
2. **只追加**：Thesis、持仓事件、决策、对话消息都是历史，不静默改写。
3. **可追溯**：每次分析固定证件版本、持仓快照、行情时间与模型。
4. **对话是思考空间，Thesis 是承诺**：聊天只读；正式变更由用户在独立编辑器中确认后生效，AI 润色只改表达、不改事实。
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
   OKX Market Provider · OpenAI-compatible LLM · Email
              |
     Scheduler → Worker → Agent Run → Decision → Notification
```

- **Headless 核心 + 薄表面**：业务规则只在应用服务与 Runtime 中。
- **单租户**，保留 `user_id`，首版不做注册登录。
- **PostgreSQL 任务表 + 独立 Worker**，不引入 Celery/Redis。
- 金额与价格：`NUMERIC` / `Decimal`，禁止浮点。

## 技术栈

Python 3.12 · FastAPI · SQLAlchemy 2.0 async · Pydantic v2 · Alembic · PostgreSQL 16 · Vue 3 + TypeScript + Vite + ECharts · Docker Compose · pytest · GitHub Actions

## 快速开始

前置：Docker + Docker Compose；本机开发另需 pyenv 与 nvm。

```bash
# Python：项目专用 pyenv virtualenv
pyenv virtualenv 3.12.8 thesium
pyenv local thesium
python -m pip install -e "backend[dev]" -i https://mirrors.aliyun.com/pypi/simple/

# Node：读取 .nvmrc
nvm use            # 24.21.0
cd frontend && npm install && cd ..

# 一键启动 Postgres + API + worker + web
cp .env.example .env
make up
# http://127.0.0.1:8080
```

### 本地开发（当前推荐）

只让 Postgres 跑在 Docker 里，API/Worker/Web 在本机运行：

```bash
# 1) 启动 Postgres（已存在则跳过）
docker compose -f deploy/docker-compose.yml --env-file .env up -d postgres

# 2) 迁移 + seed
cd backend && python -m alembic upgrade head && python -m app.scripts.seed && cd ..

# 3) API（OKX 需要代理时）
cd backend
HTTPS_PROXY=http://127.0.0.1:7897 HTTP_PROXY=http://127.0.0.1:7897 \
  NO_PROXY=127.0.0.1,localhost python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# 4) Worker + 调度器（另一个终端）
cd backend
HTTPS_PROXY=http://127.0.0.1:7897 HTTP_PROXY=http://127.0.0.1:7897 \
  NO_PROXY=127.0.0.1,localhost python -m app.workers.main

# 5) Web（另一个终端）
nvm use
cd frontend && npm run dev -- --host 127.0.0.1
```

打开 http://127.0.0.1:5173/products/btc 。产品页包含行情、持仓、Decision、通知记录与 Thesis 入口；顶部「对话」进入只读聊天。

> Worker 会按产品的 `monitor_interval_minutes` 自动排队分析。没有配置 LLM 时调度器会保持安静；配置后下一轮自动开始。重复 tick 由 `jobs` 表唯一键与 `FOR UPDATE SKIP LOCKED` 防重。

OKX 在当前网络需要代理时，API 与 Worker 启动前都要设置 `HTTPS_PROXY`（例如 `HTTPS_PROXY=http://127.0.0.1:7897`）。

AI 润色/整理需要 OpenAI 兼容模型。打开 http://127.0.0.1:5173/settings 配置：

- Base URL（如 `https://api.deepseek.com/v1`）
- Model（如 `deepseek-chat`）
- API Key

配置保存到 PostgreSQL，API Key 加密存储、前端只显示末 4 位；支持「测试连接」。测试可以使用尚未保存的表单值，且不会写库；API Key 留空时回退到已保存的 Key。保存后立即生效，无需重启 API。

本地开发会用 `backend/.thesium-secret` 自动生成加密密钥（已 gitignore）。Docker/自托管建议在 `.env` 设置 `THESIUM_SECRET_KEY`，否则重建容器会丢失密钥、已保存的 API Key 需要重新输入：

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

环境变量 `THESIUM_LLM_BASE_URL/MODEL/API_KEY` 仍可作为数据库未配置时的回退；`GET /api/v1/settings/llm` 可查看当前来源与状态。未配置时手动编辑 Thesis 不受影响，AI 按钮会提示去 Settings。

### 邮件与通知

在 http://127.0.0.1:5173/settings 的「邮件通知」里配置 SMTP：

- Host / Port / Username / Password
- From address（发件人）与 To address（收件人，留空则用发件人）
- STARTTLS（常用 587）或 SSL（常用 465）

点「发送测试邮件」会使用当前表单值发送，不写库；保存后 `verified_at` 在测试成功时记录。密码用 Fernet 加密存储，前端不回显。通知偏好也在同一页：开关决策/风险/邮件、免打扰时段、每日上限与冷却时间。

通知由程序裁决，模型只建议：

- 普通 WAIT / HOLD：不发；
- HOLD→SELL 等类别跃迁、`priority=HIGH/URGENT`、Thesis 转 `CONFLICTING`、风险预算突破：进入通知；
- 免打扰、4 小时冷却、每日上限、完全相同结论：落 `SKIPPED` 并记录原因；
- 邮件失败按 1/5/30 分钟重试 3 次，Web 通知中心可见并可手动重试。

### 只读对话

产品页顶部「对话」进入 Web 聊天。回答会带来源与时间戳，底部可打开「Run 详情」查看当时的 Thesis 版本、持仓/行情快照与模型。对话没有写工具：

- 要求改 Thesis / 记成交 / 下单 → 明确拒绝并指路；
- 模型若误称「已帮你改」，服务端后置检查会追加只读更正；
- 同一会话同一时间只跑一轮；断线后已生成部分以 `PARTIAL` 落库，可用 `after_seq` 补齐。

> Docker Hub 不可达时，在 `.env` 里把 `PYTHON_IMAGE` / `NODE_IMAGE` / `NGINX_IMAGE` / `POSTGRES_IMAGE` 指到可用镜像（示例见 `.env.example`），无需改 Dockerfile。

常用命令：`make logs`、`make migrate`、`make test`、`make dev-api`、`make dev-web`。备份：`make backup`（写入 `backups/`，用 `pg_dump`）。

## 文档

| 文档 | 内容 |
|---|---|
| [设计文档索引](docs/design/README.md) | 阅读顺序与当前结论 |
| [00 · 架构决策](docs/design/00-decisions.md) | D1–D22，含对话/渠道/润色/永续边界 |
| [01 · 领域模型](docs/design/01-domain-model.md) | 聚合、不变量、ER 图、表与索引 |
| [02 · Investment Thesis](docs/design/02-thesis.md) | 结构化 Schema、分级确认、版本状态机 |
| [03 · Agent Runtime](docs/design/03-agent-runtime.md) | Prompt 分层、工具契约、Run 生命周期 |
| [04 · 决策与通知](docs/design/04-decisions-notifications.md) | Decision Schema、通知策略 |
| [05 · REST API](docs/design/05-api.md) | 接口、SSE、错误与幂等约定 |
| [06 · 路线图](docs/design/06-roadmap.md) | P0–P7、测试、风险与验收 |
| [07 · 对话与多渠道](docs/design/07-conversation-and-channels.md) | 对话域、飞书接入、安全、语气 |

## 状态

**P0–P5 已完成。** 行情、现货/永续持仓、Thesis 版本与 AI 润色、定时分析、Decision、通知策略与邮件、Web 只读对话、Run 回放均已接通。P6 在收尾：首页当前产品概览、通知中心、Run 详情已加；下一步是验收场景、移动端细节和文档。飞书（v1.1）按当前决定暂缓。

## 许可证

[AGPL-3.0](LICENSE)。