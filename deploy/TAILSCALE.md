# 用 Tailscale 访问 Thesium（无域名 / 无公网端口）

适用场景：Thesium 跑在本地 NAS 或云主机，手机（iOS/Android）远程访问，不申请域名、不把 Web 暴露到公网。

Tailscale 基于 WireGuard，会给每台设备一个私有 IP，并负责 NAT 穿透；手机和 NAS 登录同一个 tailnet 后，就像在同一个局域网里。Thesium 不需要公网 IP，也不需要 HTTPS 证书。

## 1. 先验证 Tailscale 在当前网络可用

在中国大陆，Tailscale 的官方协调服务器 / DERP 中继可能不稳定。先在 iPhone 蜂窝网络和 Wi-Fi 下各测试一次：

- App Store 安装 **Tailscale**；
- 登录同一个账号；
- 打开 VPN；
- 访问另一台已登录 Tailscale 的设备（例如 NAS 的 Tailscale IP）的任意服务。

如果一直连不上，先不要继续；可考虑 Headscale（自建协调服务器）或 WireGuard 方案，见文末。

## 2. NAS / 云主机安装 Tailscale

以 Linux NAS 或云主机为例：

```bash
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up
```

登录后查看本机 Tailscale IP：

```bash
tailscale ip -4
# 例如 100.101.102.103
```

在 Tailscale 管理后台开启 **MagicDNS**，之后可以用机器名代替 IP。

## 3. Thesium 保持只监听本机

`deploy/docker-compose.yml` 的 web 端口默认是：

```yaml
ports:
  - "127.0.0.1:8080:80"
```

保持这样即可。Tailscale 和 Thesium 在同一台 NAS/云主机上，Tailscale 可以访问本机 `127.0.0.1:8080`，但公网无法访问 8080。

启动：

```bash
make up
```

## 4. 用 Tailscale Serve 暴露给 tailnet

在 NAS/云主机上执行：

```bash
# 方式 A：Tailscale 自动 HTTPS（地址形如 https://nas-name.tailnet-name.ts.net）
tailscale serve --bg http://127.0.0.1:8080

# 方式 B：只走 HTTP（不申请证书；流量仍由 WireGuard 加密）
tailscale serve --bg --http=80 http://127.0.0.1:8080
```

查看地址：

```bash
tailscale serve status
```

停止：

```bash
tailscale serve reset
```

> 不要把 `tailscale serve` 换成 `tailscale funnel`。Funnel 会把服务暴露到公网，和这里的目标相反。

## 5. iOS 访问

1. iPhone 安装 Tailscale，登录同一个账号，打开 VPN；
2. Safari 打开：
   - `https://<nas-name>.<tailnet>.ts.net`（方式 A），或
   - `http://<tailscale-ip>` / `http://<nas-name>`（方式 B / MagicDNS）；
3. 可以「添加到主屏幕」，当作一个 Web App 使用。

注意事项：

- iOS 同时只能启用一个 VPN；如果开着别的 VPN/代理，需要先切到 Tailscale；
- Tailscale 在后台可能被系统挂起，打开 App 或重新连接即可；
- 手机网络切换（Wi-Fi ↔ 5G）时 Tailscale 会自动重连。

## 6. 安全建议

Tailscale 已经把服务限制在 tailnet 内，但仍建议：

- Tailscale 账号开启 MFA；
- 开启设备审批 / 设备过期策略；
- 用 ACL 限制只有你的设备能访问 NAS 的 8080/443；
- **不要启用 Funnel**；
- 阿里云安全组不要放行 8080/80/443 给公网；只保留 SSH 给你自己的 IP；
- NAS 防火墙不要额外把 8080 暴露到局域网/公网；
- 即使走 Tailscale，也可以在 Nginx 上再加 Basic Auth 作为第二层（可选）；
- `THESIUM_SECRET_KEY` 固定并备份；`.env` 权限 600；备份加密。

## 7. 如果 Tailscale 不可用

按优先级：

1. **Headscale**：在阿里云自建协调服务器，iOS/Android 继续用 Tailscale 客户端；需要自己维护 DERP 中继；
2. **WireGuard**：阿里云作为 hub，NAS 和手机都连它；更底层，但配置更多；
3. **frp / 公网反代 + Basic Auth**：会暴露公网 HTTP，不建议在没有 HTTPS 的情况下使用。

不要用「前端加密码」代替网络层鉴权；API 可以被直接调用。
