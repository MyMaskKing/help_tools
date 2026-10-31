# QQ AI Bot 语音升级

## 内容
- `bot.py`：基于原 bot.py 的完整替换版，保留角色/历史/主动陪伴，增加私聊语音 ASR + TTS。
- `Dockerfile`、`requirements.txt`：容器构建依赖。

## 重要说明
1. Bot 使用 `network_mode: host`，NapCat 保持 bridge。
2. NapCat `get_record` 返回的文件路径必须能被 Bot 访问。把 NapCat 的 `./data/QQ` 同一宿主机目录额外挂载到 NapCat `/napcat-qq-data`，并挂载到 Bot `/napcat-qq-data`。
3. `NAPCAT_PATH_PREFIX` 默认 `/app/.config/QQ`；`NAPCAT_DATA_DIR` 默认 `/napcat-qq-data`。如果 NapCat 返回路径不是 `/app/.config/QQ/...`，需按返回路径调整 prefix/映射。
4. NapCat bridge 容器访问 host 网络服务默认使用 `172.17.0.1`。如果你的 Docker 网桥网关不同，调整 `AUDIO_PUBLIC_BASE`。
5. 首次启动会下载 Whisper tiny 模型，需要网络；Edge TTS 也需要网络。
6. ASR 首次启动/模型下载可能耗时较长。
7. 当前主动联系规则：闲置4小时、间隔12小时、每天最多2条、08:00-23:00，保留原设置。

## NapCat compose 增加挂载
在 napcat 的 volumes 下追加（源目录与 `./data/QQ` 相同）：
```yaml
- ./data/QQ:/napcat-qq-data:ro
```

## Bot compose 示例
在 `/root/docker-compose/ai-bot/python-qq/docker-compose.yml` 中使用：
```yaml
services:
  qwen-qq-bot:
    build: .
    container_name: qwen-qq-bot
    network_mode: host
    environment:
      - WS_URL=ws://127.0.0.1:3010
      - WS_TOKEN=cyj123456
      - OLLAMA_URL=http://127.0.0.1:11434
      - OLLAMA_MODEL=qwen25-1.5b:latest
      - NAPCAT_PATH_PREFIX=/app/.config/QQ
      - NAPCAT_DATA_DIR=/napcat-qq-data
      - AUDIO_PUBLIC_BASE=http://172.17.0.1:8123
      - AUDIO_HTTP_PORT=8123
      - WHISPER_MODEL=tiny
      - WHISPER_DEVICE=cpu
      - WHISPER_COMPUTE=int8
      - TTS_VOICE=zh-CN-XiaoxiaoNeural
      - TZ_NAME=Asia/Shanghai
    volumes:
      - ./data:/app/data
      - /root/docker-compose/QQ/data/QQ:/napcat-qq-data:ro
      - ./audio:/app/audio
      - ./models:/app/models
    restart: unless-stopped
```
注意：`/root/docker-compose/QQ/data/QQ` 要替换成 NapCat compose 所在目录下 `./data/QQ` 的真实绝对路径（如果你的目录确实是该路径则无需改）。

## 构建启动
```bash
cd /root/docker-compose/ai-bot/python-qq
docker compose up -d --build
docker compose logs -f qwen-qq-bot
```

## 测试
- 私聊文字：“你是谁呀？”
- 私聊语音：“今天有点累”
- 日志应出现 `[ASR] ... text='今天有点累'`
- Bot 会先发送语音，再发送对应文字。
