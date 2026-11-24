# Thesium 阿里云轻量应用服务器部署手册

目标：Ubuntu 24.04 + Docker Compose + 主机 Clash + Tailscale。  
Thesium 不开放公网 Web 端口；手机通过 Tailscale 私有网络访问。

> 适用：阿里云轻量应用服务器、ECS、自建 NAS。  
> 不适用：没有 Tailscale/WireGuard 的纯公网 IP 直接访问；当前版本没有应用登录，不能裸奔。

---

## 0. 架构

```text
iPhone (Tailscale App)
        │  WireGuard 加密
        ▼
Aliyun Ubuntu 24.04
  ├─ tailscaled / tailscale serve  → 127.0.0.1:8080
  ├─ Docker
  │   ├─ web (Nginx)              127.0.0.1:8080
  │   ├─ api                      内部 8000
  │   ├─ worker                   内部
  │   └─ postgres                 内部 5432
  └─ Clash mixed-port 37890
        └─ OKX / LLM / RSS 出口
```

安全边界：

- 公网只开 SSH 22（最好限制来源 IP）；
- 不开放 80/443/8080/8000/5432/37890；
- Tailscale 只对 tailnet 暴露；
- Docker 的 Postgres/API 不发布端口。

---

## 1. 阿里云安全组

轻量应用服务器 → 防火墙/安全组，入方向只保留：

| 端口 | 来源 | 用途 |
|---|---|---|
| TCP 22 | 你的固定 IP / VPN 地址 | SSH |
| UDP 41641 | 可选，0.0.0.0/0 | Tailscale 直连（不配也能走 DERP） |

不要放行：

- 80 / 443（除非以后自己加 HTTPS 反向代理）
- 8080 / 8000 / 5432
- 37890（Clash）

出方向默认全部放行即可。

---

## 2. 安装 Docker（Ubuntu 24.04）

```bash
sudo apt update
sudo apt install -y docker.io docker-compose-v2
sudo systemctl enable --now docker
sudo usermod -aG docker "$USER"
```

重新登录 SSH，或执行：

```bash
newgrp docker
docker version
docker compose version
```

如果 `docker-compose-v2` 不存在，使用 Docker 官方源安装：

```bash
sudo apt install -y ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
  | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
https://download.docker.com/linux/ubuntu noble stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

Docker Hub 慢/不可达时，在阿里云容器镜像服务控制台获取加速地址，写入：

```bash
sudo tee /etc/docker/daemon.json >/dev/null <<'JSON'
{
  "registry-mirrors": ["https://<你的阿里云镜像加速地址>"]
}
JSON
sudo systemctl restart docker
```

---

## 3. 配置 Clash 供 Docker 使用

Thesium 的 API/Worker 在容器里，需要访问宿主机 Clash 的 mixed-port。

检查 Clash 监听地址：

```bash
ss -lntp | grep 37890
```

如果显示 `127.0.0.1:37890`，容器访问不到。修改 Clash/Mihomo 配置：

```yaml
mixed-port: 37890
allow-lan: true
bind-address: '*'
```

重启 Clash 服务（服务名可能是 `clash`、`mihomo` 或你自建的服务）：

```bash
sudo systemctl restart clash
# 或
sudo systemctl restart mihomo
```

验证宿主机：

```bash
curl -x http://127.0.0.1:37890 -sS -m 10 -o /dev/null \
  -w '%{http_code}\n' \
  'https://www.okx.com/api/v5/market/ticker?instId=BTC-USDT'
```

返回 `200` 即可。

> **建议关闭 Clash TUN 模式**，只使用 mixed-port。  
> TUN 会和 Docker 网络、Tailscale 路由互相干扰。如果必须开 TUN，需要给 `100.64.0.0/10` 和 `ts.net` 加绕过规则，复杂度明显更高。

安全组已禁止 37890 入站；不要在公网放行它。

---

## 4. 上传项目

在本地项目根目录执行（把 `<SERVER_IP>` 换成阿里云公网 IP）：

```bash
rsync -av --delete \
  --exclude '.git' \
  --exclude '.env' \
  --exclude 'frontend/node_modules' \
  --exclude 'frontend/.npm-cache' \
  --exclude 'backend/.venv' \
  --exclude 'backend/__pycache__' \
  --exclude 'backups' \
  ./ root@<SERVER_IP>:/opt/thesium/
```

或者服务器上 `git clone` 你的仓库。

> 当前 `docker-compose.prod.yml` 使用 `build:`，服务器上必须有源码树：
> `backend/`、`frontend/`、`deploy/`、`backend/pyproject.toml`、`frontend/package-lock.json` 等。
> 只复制一个 compose 文件 + `.env` 是构建不出来的。
>
> `.env` 不在仓库里，要单独在服务器上创建；不要把本地 `.env` 一起 rsync 过去。

服务器上：

```bash
cd /opt/thesium
ls deploy/docker-compose.prod.yml deploy/env.production.example
ls backend/app frontend/src
```

---

## 5. 创建 .env

```bash
cd /opt/thesium
cp deploy/env.production.example .env
```

生成两个密钥：

```bash
# Postgres 密码
openssl rand -hex 24

# Fernet 密钥（加密 LLM Key / SMTP 密码）
python3 -c "import base64,os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())"
```

编辑 `.env`：

```bash
nano .env
```

至少修改：

```dotenv
POSTGRES_PASSWORD=<上面生成的密码>
THESIUM_SECRET_KEY=<上面生成的 Fernet 密钥>
THESIUM_WEB_BASE_URL=http://127.0.0.1:8080
THESIUM_MARKET_PROXY=socks5h://host.docker.internal:37890
HTTP_PROXY=http://host.docker.internal:37890
HTTPS_PROXY=http://host.docker.internal:37890
NO_PROXY=localhost,127.0.0.1,postgres,api,web
```

`THESIUM_WEB_BASE_URL` 在 Tailscale 配好后改成手机访问的 URL（见第 7 节）。  
`THESIUM_SECRET_KEY` 必须备份；丢失后需要重新输入 LLM Key 和 SMTP 密码。

权限：

```bash
chmod 600 .env
```

---

## 5.1 镜像放哪里？

单台阿里云轻量服务器，优先 **直接在服务器上构建**：

```bash
docker compose -f deploy/docker-compose.prod.yml --env-file .env up -d --build
```

这要求服务器上有完整源码树（项目根目录下的 `backend/`、`frontend/`、`deploy/`），因为 compose 的 `build.context: ..` 会把它们作为构建上下文。镜像存在本机 Docker 的 `/var/lib/docker`，不需要镜像仓库。缺点是换机器/重装系统要重新构建。

API/worker 的 Dockerfile 把 Python 依赖放在独立的 `base` stage：只有 `backend/pyproject.toml` 变化时才重新执行 `pip install`，日常修改 `backend/app` 只会重新 COPY 应用代码，不会重新下载 PyPI 包。Web 构建也给 `npm ci` 加了 BuildKit 缓存。首次构建仍需联网安装依赖；要强制重建依赖时用：

```bash
docker compose -f deploy/docker-compose.prod.yml --env-file .env build --no-cache api worker web
```

如果你不想在服务器上放源码，就用下面的 ACR 或 `docker save` 方式：服务器只保留 compose + `.env`，镜像从仓库/离线 tar 加载。

如果出现以下情况，建议用**阿里云容器镜像服务 ACR 个人版**：

- 服务器内存较小（1–2 GB），构建 Node/Python 镜像容易 OOM；
- 有多台机器或 CI；
- 想保留固定版本、快速回滚。

### ACR 个人版的地域问题

- 个人版实例创建时要选**地域**，镜像存储在该地域；
- 同地域 ECS 优先用 VPC 地址拉取，例如：
  `registry-vpc.cn-hangzhou.aliyuncs.com`
- 跨地域可以通过公网地址拉取，例如：
  `registry.cn-hangzhou.aliyuncs.com`，但速度/流量不如同地域，而且个人版**没有跨地域复制**；
- 生产上最合适：**ACR 实例和 ECS 在同一个地域**（例如都在杭州/上海）。
- 个人版有免费额度/仓库限制，具体以控制台为准；镜像总量不大时够用。

### 推送示例

在能构建 `linux/amd64` 镜像的机器上：

```bash
# 登录（用户名是阿里云账号全名，密码是 ACR 的固定密码/临时密码）
docker login --username=<阿里云账号> registry.cn-hangzhou.aliyuncs.com

# Apple Silicon 本机构建 x86 镜像
docker buildx build --platform linux/amd64 \
  -f deploy/Dockerfile.api \
  -t registry.cn-hangzhou.aliyuncs.com/<命名空间>/thesium-api:20261115 \
  --push .

docker buildx build --platform linux/amd64 \
  -f deploy/Dockerfile.web \
  -t registry.cn-hangzhou.aliyuncs.com/<命名空间>/thesium-web:20261115 \
  --push .
```

服务器上登录并拉取：

```bash
docker login --username=<阿里云账号> registry-vpc.cn-hangzhou.aliyuncs.com
docker pull registry-vpc.cn-hangzhou.aliyuncs.com/<命名空间>/thesium-api:20261115
docker pull registry-vpc.cn-hangzhou.aliyuncs.com/<命名空间>/thesium-web:20261115
```

然后把 `deploy/docker-compose.prod.yml` 里 api/worker/web 的 `build:` 换成：

```yaml
image: registry-vpc.cn-hangzhou.aliyuncs.com/<命名空间>/thesium-api:20261115
# web 用 thesium-web
```

或者单独写一个 `docker-compose.images.yml` 覆盖文件，启动时用：

```bash
docker compose -f deploy/docker-compose.prod.yml \
  -f deploy/docker-compose.images.yml \
  --env-file .env up -d --no-build
```

> 不建议把镜像放 Docker Hub：国内拉取慢且不稳定；ACR 同地域最合适。  
> 个人版没有跨地域复制，别把 ACR 建在离 ECS 很远的地域。

## 6. 启动 Thesium

```bash
cd /opt/thesium
docker compose -f deploy/docker-compose.prod.yml --env-file .env up -d --build
```

首次构建会拉取 Python/Node/Postgres/Nginx 镜像，可能需要几分钟。  
API 容器启动时会自动执行：

```text
alembic upgrade head
python -m app.scripts.seed
```

检查：

```bash
docker compose -f deploy/docker-compose.prod.yml --env-file .env ps
docker compose -f deploy/docker-compose.prod.yml --env-file .env logs -f api worker
```

另开一个 SSH：

```bash
curl -s http://127.0.0.1:8080/health
curl -s http://127.0.0.1:8080/api/v1/meta
curl -s -m 30 http://127.0.0.1:8080/api/v1/assets/BTC/okx-check
```

`okx-check` 返回 `ok:true` 说明容器能通过 Clash 访问 OKX。

如果失败：

```bash
# 在容器内测试 Clash
docker compose -f deploy/docker-compose.prod.yml --env-file .env exec api \
  python - <<'PY'
import httpx
print(httpx.get(
    "https://www.okx.com/api/v5/market/ticker",
    params={"instId": "BTC-USDT"},
    proxy="socks5h://host.docker.internal:37890",
    timeout=10,
).status_code)
PY
```

如果这里失败，检查第 3 节 Clash 的 `allow-lan` / `bind-address` / TUN。

---

## 7. Tailscale 注册与访问

### 7.1 注册账号

1. 打开 https://login.tailscale.com/start
2. 用 Google / GitHub / Microsoft / 邮箱注册；
3. 免费个人版足够（设备数、用户数限制对个人使用足够）。

### 7.2 在服务器安装并登录

```bash
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up --hostname=thesium --accept-dns=false
```

终端会输出一个登录 URL，复制到手机或电脑浏览器打开，登录并批准这台服务器。

`--accept-dns=false` 是为了不让 Tailscale 改写服务器 DNS，避免影响 Docker/Clash；iOS 客户端仍可使用 MagicDNS。

查看状态：

```bash
tailscale status
tailscale ip -4
```

在 Tailscale 管理后台：

- **DNS** → 开启 **MagicDNS**；
- **DNS** → 开启 **HTTPS Certificates**（如果要用 `tailscale serve` 的自动 HTTPS）；
- 设备列表里找到 `thesium`，可以关闭 key expiry（避免服务器定期需要重新登录）。

### 7.3 把 Web 暴露给 tailnet

```bash
# 推荐：Tailscale 自动 HTTPS，地址是 https://thesium.<tailnet>.ts.net
sudo tailscale serve --bg http://127.0.0.1:8080

# 如果不想用 HTTPS，也可以只走 HTTP（流量仍由 WireGuard 加密）
# sudo tailscale serve --bg --http=80 http://127.0.0.1:8080
```

查看地址：

```bash
tailscale serve status
```

示例：

```text
https://thesium.tailxxxx.ts.net/
|-- / proxy http://127.0.0.1:8080
```

把 `THESIUM_WEB_BASE_URL` 改成这个地址：

```bash
nano /opt/thesium/.env
# THESIUM_WEB_BASE_URL=https://thesium.tailxxxx.ts.net

cd /opt/thesium
docker compose -f deploy/docker-compose.prod.yml --env-file .env up -d api worker
```

> 不要用 `tailscale funnel`；它会把服务暴露到公网，和这里的目标相反。

### 7.4 iPhone 访问

1. App Store 安装 **Tailscale**；
2. 登录同一个账号；
3. 打开 VPN；
4. Safari 打开 `https://thesium.tailxxxx.ts.net`（或 HTTP 地址）；
5. 可「添加到主屏幕」。

注意：

- iOS 同时只能启用一个 VPN；如果开着别的代理，先切到 Tailscale；
- Wi-Fi/5G 切换时 Tailscale 会自动重连；
- Tailscale 后台可能被系统挂起，打开 App 即可。

### 7.5 Tailscale 在中国大陆

Tailscale 官方协调服务器/DERP 可能不稳定。先在 iPhone 蜂窝和 Wi-Fi 下分别测试。  
如果一直连不上，备选：

1. **Headscale**：在阿里云自建协调服务器，客户端仍用 Tailscale；
2. **WireGuard**：阿里云作为 hub，NAS 和手机都连它；
3. 不建议退回「公网 HTTP + Basic Auth」作为替代。

---

## 8. 首次使用配置

手机打开 Tailscale 地址后：

1. **Settings → LLM Provider**：填 Base URL / Model / API Key，测试连接；
2. **Settings → 邮件通知**：填 SMTP，发送测试邮件；
3. **Settings → 行情代理**：默认应显示 `socks5h://host.docker.internal:37890`（数据库/环境变量），点「测试行情连接」；
4. **Dashboard → 创建投资产品**：BTC；
5. **产品页 → Thesis**：写投资论点并确认；
6. **System**：确认调度器、最近 Run、日报状态；
7. **Settings → 通知偏好**：打开每日日报，时间 08:00；可点 System 的「立即发送日报」测试。

> 新服务器是全新数据库：LLM Key、SMTP、Thesis、持仓都需要重新配置/录入。  
> 老机器的数据不会自动迁移；需要的话用 `pg_dump`/`pg_restore`。

---

## 9. 安全加固清单

- 阿里云安全组：只开 22（你的 IP）+ 可选 UDP 41641；不要开 80/443/8080/8000/5432/37890；
- Tailscale：
  - 账号开启 MFA；
  - 设备审批 / ACL 限制只有你的设备可访问；
  - 不要开启 Funnel；
  - 服务器设备可关闭 key expiry；
- SSH：只允许密钥登录，禁用 root 密码登录；
- `THESIUM_SECRET_KEY` 固定并备份；`.env` 权限 600；
- 备份：`pg_dump` 加密后放对象存储；
- Docker 日志已限制大小（10MB × 3）；
- 定期更新镜像和系统；
- 不要在前端只加密码代替网络层鉴权；API 可以被直接调用。

---

## 10. 日常运维

### 查看日志

```bash
cd /opt/thesium
docker compose -f deploy/docker-compose.prod.yml --env-file .env logs -f api worker
```

### 重启

```bash
docker compose -f deploy/docker-compose.prod.yml --env-file .env restart api worker
```

### 更新代码

```bash
cd /opt/thesium
# git pull 或用 rsync 上传新代码
docker compose -f deploy/docker-compose.prod.yml --env-file .env up -d --build
```

API 启动时会自动迁移数据库。

### 备份

```bash
cd /opt/thesium
mkdir -p backups
docker compose -f deploy/docker-compose.prod.yml --env-file .env exec -T postgres \
  pg_dump -U thesium -d thesium > "backups/thesium-$(date +%Y%m%d-%H%M%S).sql"
```

备份包含 Thesis、持仓、设置和加密后的凭据；请加密保存。

### Tailscale 状态

```bash
tailscale status
tailscale serve status
```

---

## 11. 常见问题

| 现象 | 检查 |
|---|---|
| `MARKET_UNAVAILABLE` / `ConnectError` | Clash 是否 `allow-lan`、37890 是否监听、TUN 是否关闭；容器内 `okx-check` |
| `502 Bad Gateway` | `docker compose ... ps`，api 是否 healthy，日志 |
| 手机打不开 Tailscale 地址 | `tailscale status`、`tailscale serve status`、iPhone VPN 是否开启 |
| `tailscale serve` 报 HTTPS 不可用 | 管理后台开启 HTTPS Certificates，或改用 `--http=80` |
| 日报没发 | System 查看 `email_configured`、日报开关、上次状态；SMTP 测试 |
| 定时任务不跑 | System 看 `next_monitor_at`、Job 队列；服务器是否休眠/Worker 是否运行 |
| 阿里云能 SSH 但网页打不开 | 这是预期的：Web 只绑 127.0.0.1，通过 Tailscale Serve 访问 |
