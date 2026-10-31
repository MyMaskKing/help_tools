# python-qq · Bot 模块说明

> 这是整套 QQ AI 机器人的 **人格层**：负责连接 NapCat、调用 Ollama、保存记忆、语音识别（ASR）、语音合成（TTS）和主动陪伴。
>
> 第一次部署请先看上级目录的 [完整部署手册](../README.md)，本文件只说明这个目录里的代码和配置。

---

## 1. 它负责什么

```text
NapCat（QQ） ──WebSocket──▶ bot.py ──HTTP──▶ Ollama（大模型）
                              │
                              ├── SQLite：历史 / 角色 / 语音偏好 / 主动陪伴
                              ├── faster-whisper：语音 → 文字
                              ├── edge-tts：文字 → mp3
                              └── aiohttp：把 mp3 暴露给 NapCat 下载
```

具体功能：

- 接收私聊/群聊消息（群聊只处理 @ 机器人的消息）
- 为每个会话维护最近 12 条上下文
- 支持 `/帮助`、`/清空`、`/角色` 命令
- 私聊语音消息自动转文字
- 按需或按模式用语音回复（默认文字）
- 早/中/晚三个时间段主动发起关心
- 断线自动重连、语音失败自动回退文字

---

## 2. 目录内容

| 文件 | 作用 | 需要改吗 |
| --- | --- | --- |
| `bot.py` | 全部业务逻辑，单文件 | 改人格、改规则时才动 |
| `Dockerfile` | 构建镜像：Python 3.12 + ffmpeg + 依赖 | 一般不动 |
| `requirements.txt` | `aiohttp` / `websockets` / `faster-whisper` / `edge-tts` | 一般不动 |
| `docker-compose.yml` | 运行参数、挂载、环境变量 | 首次部署要检查 |
| `data/` | 运行后生成，`bot.db` | 不要删 |
| `audio/` | 运行后生成，临时 mp3 | 可删，自动清理 |
| `models/` | 运行后生成，Whisper 缓存 | 可删，会重新下载 |

---

## 3. 前置条件

启动本模块前，下面两项必须已经就绪：

1. **Ollama 已运行**，且 `docker exec -it ollama ollama list` 里有 compose 中 `OLLAMA_MODEL` 指定的模型；
2. **NapCat 已登录 QQ**，并在 WebUI 的「网络配置」里启用了 WebSocket 服务器：
   - 容器端口 `3001`（宿主机映射 `3010`）
   - Token 与 `WS_TOKEN` 一致（默认 `cyj123456`）

另外，`docker-compose.yml` 里这一行必须指向 NapCat 的真实数据目录：

```yaml
      - /root/docker-compose/QQ/data/QQ:/napcat-qq-data:ro
```

否则文字聊天能用，但语音识别会一直失败。

---

## 4. 构建与启动

```bash
cd /root/docker-compose/qq-ai-bot/python-qq

# 首次构建（3～15 分钟）
docker compose up -d --build

# 看日志
docker compose logs -f qwen-qq-bot
```

日常重启（不重新构建）：

```bash
docker compose restart
```

改了 `bot.py`、`Dockerfile`、`requirements.txt` 后：

```bash
docker compose up -d --build
```

---

## 5. 环境变量

在 `docker-compose.yml` 的 `environment:` 下配置；未写的使用 `bot.py` 里的默认值。完整说明见 [主文档第 10 章](../README.md#10-环境变量大全)。

| 变量 | 本目录 compose 的值 | 说明 |
| --- | --- | --- |
| `WS_URL` | `ws://127.0.0.1:3010` | NapCat WebSocket 地址 |
| `WS_TOKEN` | `cyj123456` | 必须和 NapCat 网络配置一致 |
| `OLLAMA_URL` | `http://127.0.0.1:11434` | Ollama 地址 |
| `OLLAMA_MODEL` | `qwen25-1.5b:latest` | 必须和 `ollama list` 一致 |
| `NAPCAT_PATH_PREFIX` | `/app/.config/QQ` | NapCat 返回路径的前缀 |
| `NAPCAT_DATA_DIR` | `/napcat-qq-data` | Bot 里 NapCat 数据的挂载点 |
| `AUDIO_PUBLIC_BASE` | `http://172.17.0.1:8123` | NapCat 下载语音用的地址 |
| `AUDIO_HTTP_PORT` | `8123` | 语音文件服务端口 |
| `WHISPER_MODEL` | `tiny` | `tiny` / `base` / `small` |
| `WHISPER_DEVICE` | `cpu` | 有 CUDA 可改 `cuda` |
| `WHISPER_COMPUTE` | `int8` | CPU 用 `int8` |
| `TTS_VOICE` | `zh-CN-XiaoshuangNeural` | **建议改成 `zh-CN-XiaoyiNeural`** |
| `TTS_RATE` | `-5%` | 语速 |
| `TTS_PITCH` | `+2Hz` | 音调 |
| `TTS_VOLUME` | `+0%` | 音量 |
| `TZ_NAME` | `Asia/Shanghai` | 时区，影响主动陪伴 |

> ⚠️ `zh-CN-XiaoshuangNeural` 是微软 Azure 付费音色，Edge TTS 免费接口里没有。用它时启动日志会出现 `[TTS] voice NOT available`，发语音会先失败一次再回退到 `zh-CN-XiaoyiNeural`。建议直接改成 Xiaoyi。

不在 compose 里、但常用的变量：

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `DB_PATH` | `/app/data/bot.db` | SQLite 路径 |
| `HISTORY_MESSAGES` | `12` | 上下文条数 |
| `AUDIO_HTTP_HOST` | `0.0.0.0` | 语音服务监听地址 |
| `TTS_VOICE_CANDIDATES` | `zh-CN-XiaoyiNeural,zh-CN-XiaoxiaoNeural` | 备用音色 |
| `TTS_TIMEOUT` | `45` | 合成超时秒数 |
| `TTS_RETRIES` | `1` | 网络错误重试次数 |
| `AUDIO_CLEANUP_MAX_AGE` | `600` | mp3 保留秒数 |
| `AUDIO_CLEANUP_INTERVAL` | `300` | 清理间隔秒数 |
| `ASR_MIN_LOGPROB` | `-1.0` | 识别置信度阈值 |
| `ASR_MAX_NO_SPEECH` | `0.6` | 静音概率阈值 |
| `HF_ENDPOINT` | 无 | 国内建议 `https://hf-mirror.com` |

---

## 6. 启动日志与自检

健康启动的关键几行：

```text
[DB] database initialized
[ASR] Whisper ready
[TTS] voice ok: zh-CN-XiaoyiNeural
[TTS] audio server listening on 0.0.0.0:8123
[INFO] NapCat WebSocket connected
[PROACTIVE] morning/noon/evening scheduler started
```

| 缺哪一行 | 说明 |
| --- | --- |
| `[ASR] Whisper ready` | 模型没加载，语音输入不可用；加 `HF_ENDPOINT` 或换网络 |
| `[TTS] voice ok` | 音色不可用，参考第 5 节 |
| `audio server listening` | 8123 端口没起来，检查端口占用 |
| `NapCat WebSocket connected` | 检查 NapCat 网络配置、Token、3010 端口 |

---

## 7. 语音链路细节

### 7.1 语音输入（ASR）

1. 私聊发来 `record` 段；
2. Bot 调 NapCat `get_record`，请求转成 wav；
3. NapCat 返回 **容器内路径**（默认前缀 `/app/.config/QQ`）；
4. Bot 剥掉前缀，拼到自己的 `/napcat-qq-data` 上；
5. faster-whisper 识别中文。

路径映射能否成立，取决于两个容器是否挂了同一个宿主机目录（见主文档附录 B）。

识别结果会打印：

```text
[ASR] user=123456 logprob=-0.32 no_speech=0.01 lang=0.99 text='今天有点累'
```

`logprob` 太低或 `no_speech` 太高时，会回复“没太听清”。

### 7.2 语音回复（TTS）

1. `edge-tts` 合成 mp3 到 `/app/audio`；
2. 内置 HTTP 服务暴露为 `http://172.17.0.1:8123/audio/<32位hex>.mp3`；
3. 让 NapCat 发一条 `record` 消息，内容是该 URL；
4. NapCat 下载并转成 QQ 语音。

只允许 32 位十六进制文件名，避免目录遍历；文件默认 600 秒后清理。

### 7.3 失败回退

- TTS 全部音色失败 → 自动改发文字，并打日志；
- 开启持续语音模式时会先合成确认语，**发送成功才写入数据库**，避免“假开启”；
- Whisper 加载失败不影响文字聊天；
- WebSocket 断开时，挂起的请求立即失败，不会每条都等 45 秒。

---

## 8. 数据

`data/bot.db`（SQLite）包含：

| 表 | 内容 |
| --- | --- |
| `history` | 聊天记录 |
| `user_roles` | 自定义角色 |
| `proactive_contacts` | 主动陪伴状态 |
| `voice_preferences` | 语音模式开关 |

备份：

```bash
tar czf bot-data-$(date +%F).tar.gz data
```

`/清空` 只删当前会话的 `history`，不删角色。

---

## 9. 二次开发 / 调试

### 改人格

编辑 `bot.py` 里的 `SYSTEM_PROMPT`（约 170～198 行），然后：

```bash
docker compose up -d --build
```

### 改回复长度

`ollama_chat()` 的 `num_predict`（默认 220）和 `temperature`（默认 0.78）。

### 改主动陪伴时间

`PROACTIVE_SLOTS` 里的 `start` / `end`；闲置时长是 `IDLE_HOURS`（默认 4 小时）。

### 在容器里调试

```bash
# 进容器
docker exec -it qwen-qq-bot bash

# 看数据库
python -c "import sqlite3; print(sqlite3.connect('/app/data/bot.db').execute('select count(*) from history').fetchone())"

# 列可用音色
edge-tts --list-voices | grep zh-CN
```

### 验证 compose 配置

```bash
docker compose config
```

能正常打印就说明 YAML 没写错。

---

## 10. 已知限制

- 依赖 Linux 的 `network_mode: host` 和 `172.17.0.1` 网桥地址；Windows/macOS Docker Desktop 不适用。
- 群聊只处理 @ 消息，且只回文字，不识别群语音。
- 语音识别针对中文优化，其他语言效果差。
- CPU 推理 1.5B 模型通常 2～15 秒一条回复，属正常。
- 默认只回文字；发语音不等于回语音，要显式要求或开启持续语音模式。
- `tiny` 模型识别率一般，噪音环境下容易听错，可换 `small`。

---

## 11. 相对旧版 `bot.py` 的修复

当前版本在原版基础上修了这些问题（来自文件头注释）：

1. **TTS 音色不可用导致 `NoAudioReceived`**：默认音色改为 Edge 接口真实存在的音色，支持备用音色链，启动时校验并打印可用中文音色。
2. **语音模式“假开启”**：先合成确认语，成功后才写入语音偏好；失败明确告知并回退文字。
3. **音频文件永不清理**：新增后台清理协程，按修改时间删除过期 mp3。
4. **ASR 置信度判断错误**：改用 `segment.avg_logprob` / `no_speech_prob`，不再误用语种概率。
5. **Whisper 加载失败拖死整个 Bot**：语音转文字单独降级，文字聊天照常。
6. **WebSocket 断开后请求干等 45 秒**：断开时让挂起请求立即失败。
7. **主动陪伴日志刷屏**：只在进入/离开时间段时打印。
8. **语音模式否定语义错误**：“不要关闭语音模式”不再被当成关闭命令。

新增的环境变量：`TTS_VOICE_CANDIDATES`、`AUDIO_CLEANUP_MAX_AGE`、`AUDIO_CLEANUP_INTERVAL`、`ASR_MIN_LOGPROB`、`ASR_MAX_NO_SPEECH`。

---

## 12. 排错速查

| 现象 | 先看 |
| --- | --- |
| 一直 `connecting` / `reconnect` | NapCat WS 是否启用、Token、3010 端口 |
| 有消息但不回 | `[ERROR] Ollama`、模型名是否一致、Ollama 是否在跑 |
| 语音不识别 | `[ASR]` 日志、`/napcat-qq-data` 是否挂对、Whisper 是否加载 |
| 只回文字 | `[TTS]` 日志、音色是否有效、`AUDIO_PUBLIC_BASE` 是否可达 |
| 主动消息不发 | 时间段、4 小时闲置、当天是否已发、是否有历史 |
| 容器起不来 | `docker logs qwen-qq-bot`、端口占用、挂载路径 |

完整排查步骤见 [主文档第 12 章](../README.md#12-故障排查按现象查)。
