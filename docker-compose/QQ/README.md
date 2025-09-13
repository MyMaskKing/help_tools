# Napcat QQ Bot Docker 部署

## 项目介绍

Napcat 是一个基于 Mirai 的 QQ 机器人框架，支持通过 Docker 容器化部署。本项目提供了完整的 Docker Compose 配置，可以快速部署 Napcat QQ 机器人。

## 功能特性

- 🤖 基于 Mirai 的 QQ 机器人框架
- 🐳 Docker 容器化部署，简单易用
- 🌐 WebUI 管理界面
- 🔌 WebSocket 实时通信
- 📁 数据持久化存储
- 🔄 自动重启机制

## 快速开始

### 1. 环境准备

确保您的系统已安装：
- Docker
- Docker Compose

### 2. 配置环境变量

在项目根目录创建 `.env` 文件，配置以下参数：

```bash
# Napcat 用户ID和组ID（可选，默认使用容器内用户）
NAPCAT_UID=1000
NAPCAT_GID=1000
```

### 3. 启动服务

```bash
mkdir -p ./data/QQ
mkdir -p ./data/napcat/config

# 启动服务
# 有.env文件直接启动
docker-compose -f docker-compose-qq.yml up -d
# 没有.env的时候
NAPCAT_UID=$(id -u) NAPCAT_GID=$(id -g) docker compose -f docker-compose-qq.yml up -d

# 查看日志
docker-compose logs -f napcat

# 停止服务
docker-compose down
```

## 服务配置

### 端口说明

| 端口 | 用途 | 说明 |
|------|------|------|
| 3000 | WebUI | 主要管理界面 |
| 3001 | WebSocket | 实时通信接口 |
| 6099 | WebUI | 可选备用端口 |

### 数据目录

- `./data/QQ` - QQ 相关数据存储
- `./data/napcat/config` - Napcat 配置文件

### 环境变量

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| NAPCAT_UID | 容器内用户ID | 1000 |
| NAPCAT_GID | 容器内组ID | 1000 |

## 使用说明

1. **首次启动**：容器启动后，访问 `http://localhost:3000` 进入 WebUI
2. **配置机器人**：在 WebUI 中配置 QQ 账号和机器人参数
3. **查看状态**：通过 WebSocket 连接 `ws://localhost:3001` 获取实时状态
4. **数据备份**：定期备份 `./data` 目录下的数据

## 故障排除

## cUrl测试用例

1. 发送私信
```
curl -X POST "http://localhost:3009/send_private_msg" \
  -H 'Authorization: xxxx' \
  -H 'Content-Type: application/json' \
  -d '{
        "user_id":"1647470402",
        "message": "你好，这是来自 NapCatQQ 的私聊消息"
      }'
```
2. 获取好友列表
  
curl -X POST "http://localhost:3009/get_friend_list" \
  -H "Authorization: xxxx" 
```

> 补充：如果使用n8n的HTTP节点，可以直接通过curl导入

### 常见问题

1. **容器无法启动**
   - 检查端口是否被占用
   - 确认 Docker 服务是否正常运行

2. **WebUI 无法访问**
   - 检查防火墙设置
   - 确认端口映射是否正确

3. **数据丢失**
   - 检查数据目录权限
   - 确认卷挂载配置

### 日志查看

```bash
# 查看实时日志
docker-compose logs -f napcat

# 查看最近100行日志
docker-compose logs --tail=100 napcat
```

## 更新说明

```bash
# 拉取最新镜像
docker-compose pull

# 重启服务
docker-compose up -d
```

## 注意事项

- 请妥善保管 QQ 账号信息，避免泄露
- 定期备份重要数据
- 遵守 QQ 使用条款和机器人开发规范
- 建议在生产环境中使用 HTTPS

## 技术支持

如遇到问题，请查看：
- [Napcat 官方文档](https://github.com/lss233/napcat)
- [Mirai 官方文档](https://github.com/mamoe/mirai)
- 项目 Issues 页面

## 许可证

本项目遵循相应的开源许可证，请查看具体项目的许可证文件。
