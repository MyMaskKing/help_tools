## 📝 n8n Docker Compose 部署说明

### 目录结构

```
.
├── data/                     # n8n 数据存储目录（持久化存储）
└── n8n-compose.yml        # Docker Compose 配置文件
```

### 🚀 部署步骤

#### 1. 下载或克隆项目

首先，您需要下载 `n8n-compose.yml` 文件的项目。


#### 2. 配置 `n8n-compose.yml`

* **数据存储目录**：n8n 的数据将存储在当前目录下的 `data` 文件夹中。容器内的 `/home/node/.n8n` 目录映射到宿主机的 `./data`。

* **基本认证**：设置了基本认证来保护 n8n 的 Web 界面。您可以通过设置 `N8N_BASIC_AUTH_USER` 和 `N8N_BASIC_AUTH_PASSWORD` 来指定用户名和密码。

* **时区设置**：时区设置为上海（`Asia/Shanghai`），您可以根据需要修改。

* **内存限制**：为了限制容器的内存占用，设置了内存限制（512MB）。可以根据实际需要进行调整。

* **HTTPS限制**：如果您确定当前环境是安全的，并且无法使用 HTTPS，可以通过设置环境变量`environment `来禁用安全 Cookie `N8N_SECURE_COOKIE=false`

#### 3. 创建数据目录并设置权限

确保宿主机上的 `./data` 目录存在，并具有正确的权限。

```bash
mkdir -p ./data
sudo chown -R 1000:1000 ./data
sudo chmod -R 775 ./data
```

> `1000:1000` 是容器内 `node` 用户的默认 UID 和 GID。如果您使用的是其他 UID 或 GID，请根据实际情况修改。

#### 4. 启动 n8n 服务

在 `n8n-compose.yml` 文件所在目录运行以下命令来启动 n8n 服务：

```bash
docker-compose -f n8n-compose.yml up -d
```

这将下载所需的 n8n 镜像并启动容器。

#### 5. 访问 n8n

启动成功后，您可以在浏览器中访问 n8n Web 界面：

```
http://localhost:5678
```

使用您在 `n8n-compose.yml` 文件中设置的用户名和密码进行登录。

---

### ⚙️ 配置选项说明

#### 数据存储目录

n8n 的数据被保存在宿主机的 `./data` 目录中。这样做的好处是即使容器停止或删除，数据也不会丢失。您可以根据需要修改该路径。

#### 基本认证

为了确保 n8n Web 界面的安全性，我们启用了基本认证。在 `n8n-compose.yml` 文件中，您可以通过修改以下环境变量来设置自己的用户名和密码：

```yaml
N8N_BASIC_AUTH_USER=admin
N8N_BASIC_AUTH_PASSWORD=your_secure_password
```

#### 内存限制

为了控制容器的内存使用，设置了内存上限为 512MB。如果您认为需要更多的内存，您可以修改 `deploy.resources.limits.memory` 为适合的值：

```yaml
resources:
  limits:
    memory: 512M  # 修改为适合的值，例如 1G
```

#### 时区设置

n8n 的时区已经设置为 `Asia/Shanghai`。如果您希望使用其他时区，请修改以下环境变量：

```yaml
TZ=Asia/Shanghai
```

#### 保存执行数据

`EXECUTIONS_DATA_SAVE_ON_ERROR=all` 配置指示 n8n 在执行失败时保存执行数据。这将帮助您调试失败的任务。如果不需要保存失败的数据，可以将其设置为 `none`。

#### 二进制数据存储

`N8N_DEFAULT_BINARY_DATA_MODE=filesystem` 表示将二进制数据存储在文件系统中，而不是内存中。这可以减少内存占用，适合生产环境。

#### 禁用安全 Cookie（不推荐）
```
environment:
  - N8N_SECURE_COOKIE=false
```

---

### 🛠️ 其他常用命令

* **查看容器状态**：

  ```bash
  docker-compose ps
  ```

* **查看日志**：

  ```bash
  docker-compose logs -f
  ```

* **停止服务**：

  ```bash
  docker-compose down
  ```

* **删除所有容器、网络和卷**：

  ```bash
  docker-compose down --volumes
  ```

---

### 🔒 配置 HTTPS（可选）

为了确保您的 n8n 服务通过 HTTPS 安全访问，建议使用 Nginx 或 Traefik 作为反向代理，配置 TLS/SSL。这里推荐使用免费的 [Let's Encrypt](https://letsencrypt.org/) 证书来配置 HTTPS。

---

### 🎯 其他注意事项

* **定期备份**：为了避免数据丢失，请定期备份 `./data` 目录中的文件。
* **资源监控**：使用 `docker stats` 监控容器的资源使用情况，确保内存和 CPU 使用符合预期。
* **更新 n8n 镜像**：您可以通过 `docker-compose pull` 拉取最新的 n8n 镜像并更新服务。

---
