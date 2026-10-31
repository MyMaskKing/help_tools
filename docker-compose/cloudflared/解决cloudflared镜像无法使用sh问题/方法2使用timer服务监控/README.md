# Cloudflared 健康自愈监控（方法 2：宿主机 systemd timer）

用宿主机上的 systemd timer 每 5 分钟检查一次 `cloudflared` 容器，不健康就自动 `docker restart`，连续失败 3 次后暂停 3 小时并通过 QQ 机器人发通知。

---

## 一、这个方案解决什么问题

官方 `cloudflare/cloudflared` 镜像是 **distroless / scratch 基础镜像，里面没有 `sh`、没有 `curl`、没有 `grep`**。后果是：

- compose 里写的 `healthcheck: ["CMD", "curl", ...]` 在这个镜像里根本跑不起来，容器永远处于 `unhealthy`
- 你也没法 `docker exec -it cloudflared sh` 进去排查（这就是目录名里"无法使用 sh"的由来）
- 容器挂了、隧道断了，`restart: always` 也未必能把你救回来，往往是人肉发现

两个解法：

| 方法 | 思路 | 目录 |
|---|---|---|
| 方法 1 | 基于 alpine 自建镜像，把 `cloudflared` 二进制拷进去，补上 `curl`/`grep`/`sh`，让容器内 healthcheck 真正可用 | `../方法1使用alpine镜像基础嵌入cloudflared/` |
| **方法 2（本文）** | **不动镜像**，在宿主机上用 systemd timer 定时检查、定时重启、定时告警 | 当前目录 |

方法 2 的好处是零侵入、不重新构建镜像；代价是检查粒度最细到 5 分钟，且依赖宿主机上的 `docker`、`curl`、`grep`。

---

## 二、文件说明

| 文件 | 作用 |
|---|---|
| `check_cloudflared.sh` | 主逻辑：查健康状态 → 失败计数 → 重启 → 超限暂停 → webhook 通知 |
| `check_cloudflared.service` | systemd 一次性服务（`Type=oneshot`），执行上面的脚本，输出追加到 `/var/log/check_cloudflared.log` |
| `check_cloudflared.timer` | 定时器：开机 5 分钟后首次运行，之后每 5 分钟一次 |

运行时的状态文件放在 `/var/lib/docker-health-monitor/`：

- `<容器名>.count` —— 当前连续失败次数
- `<容器名>.lastfail` —— 达到上限时的时间戳，用来计算 3 小时暂停期

---

## 三、前置条件

1. **被监控的容器必须有一个能真正通过的 healthcheck**。
   因为脚本的判定依据是 `docker inspect --format '{{.State.Health.Status}}'`，没有 healthcheck 的容器这一项取不到值，会被判成不健康并反复重启。
   → 所以方法 2 实际要配合**方法 1 构建的 `cloudflared_custom` 镜像**使用（它自带 `curl`，healthcheck 能跑通）。

   先确认一下：

   ```bash
   docker inspect --format '{{.State.Health.Status}}' cloudflared_custom
   # 期望输出：healthy
   ```

2. **cloudflared 要开着 metrics 端口**，默认 `localhost:2000`：

   ```bash
   curl -s http://localhost:2000/metrics | grep cloudflared_tunnel_ha_connections
   # 期望看到类似：cloudflared_tunnel_ha_connections 4
   ```

   这要求 compose 里带了 `--metrics localhost:2000` 且用了 `network_mode: host`（本仓库的 compose 两者都满足）。

3. 宿主机有 `docker` CLI、`curl`、`grep`、`bash`。

4. systemd 版本 ≥ 240（`StandardOutput=append:` 语法需要；Ubuntu 20.04+ / Debian 11+ 都满足）。

5. 脚本以 root 身份运行（systemd 系统级 service 默认就是 root），`docker restart` 无需额外授权。

---

## 四、部署步骤

### 第 1 步：改脚本里的配置

打开 `check_cloudflared.sh`，改这几项：

| 变量 | 默认值 | 说明 |
|---|---|---|
| `WEBHOOK_URL` | `http://localhost:3009/send_private_msg` | 你的 QQ 机器人（NapCat / go-cqhttp）上报地址 |
| `MONITORED_CONTAINERS` | `("cloudflared_custom")` | 要监控的容器名，可以有多个 |
| `RESTART_LIMIT` | `3` | 连续失败重启次数上限 |
| `PAUSE_AFTER_LIMIT` | `10800` | 达到上限后暂停多少秒（10800 = 3 小时） |
| `STATE_DIR` | `/var/lib/docker-health-monitor` | 状态文件目录，一般不用改 |
| `CLOUDFLARED_READY_URL` | `http://localhost:2000/metrics` | cloudflared 的 metrics 地址 |

还有两处是**硬编码的，必须改成你自己的**，否则通知发不出去（但也只是通知失败，不影响重启逻辑）：

```bash
# send_webhook() 里
local payload="{ \"user_id\": 1647470402, \"message\": \"${escaped_message}\" }"   # 改成你的 QQ 号
-H "Authorization: xxx" \                                                          # 改成你的 token
```

### 第 2 步：安装脚本和 unit

```bash
# 脚本放到 PATH 里（service 里写的就是这个绝对路径）
sudo install -m 755 check_cloudflared.sh /usr/local/bin/check_cloudflared.sh

# unit 文件
sudo install -m 644 check_cloudflared.service /etc/systemd/system/
sudo install -m 644 check_cloudflared.timer   /etc/systemd/system/
```

### 第 3 步：启用定时器

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now check_cloudflared.timer
```

### 第 4 步：验证

```bash
# 定时器已生效，能看到下次触发时间
systemctl list-timers | grep cloudflared

# 立刻手动跑一次，不用等 5 分钟
sudo systemctl start check_cloudflared.service

# 看结果
sudo tail -f /var/log/check_cloudflared.log
```

正常会看到类似：

```
Fri Oct 31 18:30:01 CST 2026: cloudflared_custom readiness HTTP Response: healthy
Fri Oct 31 18:30:01 CST 2026: cloudflared_custom 健康状态正常
```

---

## 五、日常怎么用

### 查看运行状态

```bash
systemctl status check_cloudflared.timer          # 定时器状态
systemctl list-timers check_cloudflared.timer     # 下次/上次运行时间
sudo systemctl status check_cloudflared.service   # 最近一次执行的退出码
journalctl -u check_cloudflared.service -n 50     # 从 journal 看（补充日志文件）
```

### 看检查日志

```bash
sudo tail -n 100 /var/log/check_cloudflared.log
sudo tail -f  /var/log/check_cloudflared.log      # 实时跟随
```

### 手动触发一次检查

```bash
sudo systemctl start check_cloudflared.service
```

### 临时改检查频率

不用改 timer 文件，直接跑一次性的 `systemd-run`：

```bash
sudo systemd-run --on-active=30s --unit=manual-check /usr/local/bin/check_cloudflared.sh
```

或者临时把 timer 间隔调成 1 分钟（改完要 `daemon-reload` 并重启 timer）：

```bash
sudo systemctl edit --full check_cloudflared.timer
# 把 OnUnitActiveSec=5min 改成 1min
sudo systemctl daemon-reload && sudo systemctl restart check_cloudflared.timer
```

### 只想关掉 QQ 通知

不用停监控，把 `send_webhook()` 的函数体注释掉，或者把 `WEBHOOK_URL` 改成空字符串即可。

---

## 六、怎么关闭

按"关到什么程度"分四种，选一种就行。

### 1）临时停止（本次开机内有效）

```bash
sudo systemctl stop check_cloudflared.timer
```

> 注意：重启机器后会**自动恢复**，因为 `enable` 状态还在。

### 2）永久停止（开机不再启动）

```bash
sudo systemctl disable --now check_cloudflared.timer
```

脚本和 unit 文件都还在，只是不再定时运行。想恢复：

```bash
sudo systemctl enable --now check_cloudflared.timer
```

### 3）彻底卸载

```bash
sudo systemctl disable --now check_cloudflared.timer
sudo rm -f /etc/systemd/system/check_cloudflared.service /etc/systemd/system/check_cloudflared.timer
sudo systemctl daemon-reload
sudo systemctl reset-failed

# 清理运行痕迹（失败计数、暂停标记、日志）
sudo rm -rf /var/lib/docker-health-monitor
sudo rm -f  /var/log/check_cloudflared.log
```

### 4）只停某一台容器的监控（最不粗暴）

编辑 `/usr/local/bin/check_cloudflared.sh`，从数组里去掉对应名字：

```bash
MONITORED_CONTAINERS=("cloudflared_custom")   # 改成 ("") 即全部跳过
```

不需要动 systemd。注意改的是 `/usr/local/bin/` 下那份，不是仓库里这份。

### 5）紧急止血：立刻停止一切重启行为

如果你怀疑是脚本在反复重启容器，想让它在任何时候都不能再动手：

```bash
sudo systemctl stop check_cloudflared.timer
sudo systemctl mask check_cloudflared.timer    # 连手动 start 也会被拒绝，最彻底
```

解除：

```bash
sudo systemctl unmask check_cloudflared.timer
```

### 6）卡在"暂停重启 3 小时"状态，想立刻恢复

删掉暂停标记，下一次运行就会重新开始计数：

```bash
sudo rm -f /var/lib/docker-health-monitor/*.lastfail
sudo rm -f /var/lib/docker-health-monitor/*.count
```

---

## 七、已知限制与坑

### 1）`http_response` 算了但没用于判定（重要）

脚本里对 cloudflared 专门查了 metrics：

```bash
http_response=$(curl -s ${CLOUDFLARED_READY_URL} | grep -E '^cloudflared_tunnel_ha_connections [1-9]')
```

但后面决定要不要重启时，用的仍然是 `health_status`（来自 `docker inspect`），`http_response` 只被打进了日志。也就是说：

- 如果监控的是**方法 1 的 `cloudflared_custom`**（healthcheck 可用）→ 没有问题
- 如果监控的是**官方 `cloudflared` 镜像**（healthcheck 必然失败）→ 会被每 5 分钟重启一次，直到触发 3 次上限后暂停 3 小时

要用官方镜像的话，判定那行需要改成优先看 `http_response`：

```bash
# 把
if [ "$health_status" != "healthy" ]; then
# 换成
[ "$cname" == *cloudflared* ] && effective="$http_response" || effective="$health_status"
if [ "$effective" != "healthy" ]; then
```

### 2）没有 healthcheck 的容器会陷入重启循环

`docker inspect --format '{{.State.Health.Status}}'` 在无 healthcheck 的容器上会报错，取到空值 → 恒判为不健康 → 每 5 分钟重启一次 → 3 次后暂停 3 小时。加容器到 `MONITORED_CONTAINERS` 前，先确认它的 `.State.Health.Status` 能取到值。

### 3）状态文件残留会导致"莫名其妙不重启了"

排查时先看这两个：

```bash
ls -l /var/lib/docker-health-monitor/
cat /var/lib/docker-health-monitor/*.count
```

### 4）日志不轮转

`/var/log/check_cloudflared.log` 只增不减。长期跑建议加个 logrotate：

```bash
sudo tee /etc/logrotate.d/check_cloudflared >/dev/null <<'EOF'
/var/log/check_cloudflared.log {
    weekly
    rotate 4
    compress
    missingok
    notifempty
    copytruncate
}
EOF
```

### 5）webhook 失败不影响自愈

`send_webhook` 里 `curl` 的输出被丢弃（`>/dev/null 2>&1`），机器人挂了也照样重启容器——这是有意为之，别把通知当成依赖。

### 6）检查间隔决定恢复速度

`OnUnitActiveSec=5min` 意味着隧道挂了最多 5 分钟才被发现。要更快就调小间隔，但别小于 1 分钟，否则会和容器自身的 healthcheck（30 秒一次）打架。

---

## 八、和方法 1 的关系

```
方法 1（自建镜像）  →  容器内有 curl/grep/sh，healthcheck 真正可用
                        ↓
方法 2（本目录）    →  宿主机 timer 每 5 分钟读 health 状态，
                        失败就 docker restart，超限暂停 + QQ 告警
```

两者可以叠加用：方法 1 修好了容器内的 healthcheck，方法 2 负责"不健康就重启"和"告警"。如果只想要容器内自愈，方法 1 的 `restart: always` 加 healthcheck 已经够；如果还想要"连续失败就放弃并通知我"，就需要方法 2 这层。
