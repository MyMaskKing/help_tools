# 预构建镜像 Docker Compose 使用说明

使用预构建镜像部署闲鱼自动回复系统，所有配置都在Docker Compose文件中完成，无需依赖外部文件。

## 🚀 快速开始

### 1. 基本启动

```bash
# 创建数据目录
mkdir -p data logs backups

# 启动服务
docker-compose -f docker-compose-prebuilt.yml up -d

# 查看日志
docker-compose -f docker-compose-prebuilt.yml logs -f
```

### 2. 自定义管理员账号

修改 `docker-compose-prebuilt.yml` 中的环境变量：

```yaml
environment:
  # 管理员账号配置（可自定义）
  - ADMIN_USERNAME=myadmin          # 自定义用户名
  - ADMIN_PASSWORD=MySecurePass123  # 自定义密码
  - ADMIN_EMAIL=admin@mycompany.com # 自定义邮箱
```

然后重启服务：

```bash
docker-compose -f docker-compose-prebuilt.yml down
docker-compose -f docker-compose-prebuilt.yml up -d
```

## 🔧 功能特性

### ✅ 自动安全配置
- **隐藏默认登录信息** - 登录页面不显示默认账号
- **启用安全模式** - 系统级安全设置
- **自定义管理员账号** - 可设置自己的用户名和密码
- **自动SQL注入** - 容器启动时自动配置数据库

### ✅ 无需外部文件
- **内置SQL脚本** - 所有SQL操作都在Docker文件中
- **自动页面修改** - 自动修改登录页面隐藏默认信息
- **环境变量配置** - 通过环境变量自定义设置

## 📊 环境变量说明

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `ADMIN_USERNAME` | admin | 管理员用户名 |
| `ADMIN_PASSWORD` | admin123 | 管理员密码 |
| `ADMIN_EMAIL` | admin@example.com | 管理员邮箱 |
| `HIDE_DEFAULT_LOGIN` | true | 隐藏默认登录信息 |
| `SECURITY_MODE` | true | 启用安全模式 |

## 🔍 使用方法

### 1. 默认启动（使用默认管理员账号）

```bash
docker-compose -f docker-compose-prebuilt.yml up -d
```

访问：http://localhost:8080
- 用户名：admin
- 密码：admin123

### 2. 自定义管理员账号

```bash
# 编辑 docker-compose-prebuilt.yml
# 修改 ADMIN_USERNAME, ADMIN_PASSWORD, ADMIN_EMAIL

# 重启服务
docker-compose -f docker-compose-prebuilt.yml down
docker-compose -f docker-compose-prebuilt.yml up -d
```

### 3. 查看启动日志

```bash
# 查看所有日志
docker-compose -f docker-compose-prebuilt.yml logs

# 实时查看日志
docker-compose -f docker-compose-prebuilt.yml logs -f

# 查看特定服务日志
docker-compose -f docker-compose-prebuilt.yml logs -f xianyu-app
```

## 🛠️ 管理命令

### 启动服务
```bash
docker-compose -f docker-compose-prebuilt.yml up -d
```

### 停止服务
```bash
docker-compose -f docker-compose-prebuilt.yml down
```

### 重启服务
```bash
docker-compose -f docker-compose-prebuilt.yml restart
```

### 查看服务状态
```bash
docker-compose -f docker-compose-prebuilt.yml ps
```

### 进入容器
```bash
docker exec -it xianyu-auto-reply sh
```

## 🔄 更新镜像

### 方法1: 使用更新脚本（推荐）

**Linux/macOS:**
```bash
# 给脚本执行权限
chmod +x update-docker.sh

# 运行更新脚本
./update-docker.sh
```

**Windows:**
```cmd
# 运行更新脚本
update-docker.bat
```

### 方法2: 手动更新

```bash
# 1. 拉取最新镜像
docker-compose -f docker-compose-prebuilt.yml pull

# 2. 重新创建并启动容器
docker-compose -f docker-compose-prebuilt.yml up -d --force-recreate
```

### 方法3: 一步完成

```bash
# 拉取最新镜像并重新创建容器
docker-compose -f docker-compose-prebuilt.yml up -d --pull always
```

### 方法4: 完全重建

```bash
# 停止并删除容器
docker-compose -f docker-compose-prebuilt.yml down

# 拉取最新镜像
docker-compose -f docker-compose-prebuilt.yml pull

# 重新启动
docker-compose -f docker-compose-prebuilt.yml up -d
```

### 检查镜像版本

```bash
# 查看当前镜像信息
docker images | grep xianyu-auto-reply

# 查看容器使用的镜像
docker inspect xianyu-auto-reply | grep Image
```

## 🔒 安全特性

### 自动安全配置
1. **隐藏默认登录信息** - 登录页面不显示默认账号密码
2. **启用安全模式** - 系统级安全设置
3. **自定义管理员凭据** - 使用您设置的用户名和密码
4. **数据库安全设置** - 自动配置安全相关设置

### 数据持久化
- **数据目录**：`./data/` - 数据库和用户数据
- **日志目录**：`./logs/` - 应用日志
- **备份目录**：`./backups/` - 自动备份

## 🚨 故障排除

### 1. 端口冲突

**Ubuntu/Linux 检查端口占用：**

```bash
# 检查8080端口是否被占用
sudo netstat -tlnp | grep :8080
# 或者
sudo lsof -i :8080
# 或者
sudo ss -tlnp | grep :8080

# 如果被占用，杀死进程
sudo kill -9 <PID>
```

**Windows 检查端口占用：**

```cmd
# 检查8080端口
netstat -ano | findstr :8080

# 杀死进程
taskkill /PID <PID> /F
```

### 2. 容器启动失败

```bash
# 查看详细日志
docker-compose -f docker-compose-prebuilt.yml logs

# 检查容器状态
docker ps -a

# 重新创建容器
docker-compose -f docker-compose-prebuilt.yml down
docker-compose -f docker-compose-prebuilt.yml up -d --force-recreate
```

### 3. 数据库问题

```bash
# 进入容器检查数据库
docker exec -it xianyu-auto-reply sh
sqlite3 /app/data/xianyu_data.db "SELECT * FROM system_settings;"

# 手动执行SQL
sqlite3 /app/data/xianyu_data.db "UPDATE system_settings SET value='false' WHERE key='show_default_login_info';"
```

### 4. 登录页面问题

```bash
# 检查登录页面
docker exec -it xianyu-auto-reply cat /app/static/login.html | grep defaultLoginInfo

# 手动修改登录页面
docker exec -it xianyu-auto-reply sed -i 's/id="defaultLoginInfo" class="mt-4 p-3 bg-light rounded-3"/id="defaultLoginInfo" class="mt-4 p-3 bg-light rounded-3" style="display: none;"/g' /app/static/login.html
```

## 📈 监控和维护

### 健康检查
```bash
# 检查服务健康状态
docker-compose -f docker-compose-prebuilt.yml ps

# 查看健康检查日志
docker inspect xianyu-auto-reply | grep -A 10 Health
```

### 数据备份
```bash
# 备份数据目录
cp -r data/ backups/backup-$(date +%Y%m%d-%H%M%S)/

# 恢复数据
cp -r backups/backup-20231201-120000/data/ ./
```

## 🎯 优势

- ✅ **零依赖** - 不需要外部文件
- ✅ **自动配置** - 启动时自动完成所有设置
- ✅ **安全默认** - 默认隐藏敏感信息
- ✅ **可自定义** - 通过环境变量自定义设置
- ✅ **数据持久化** - 配置和数据持久保存
- ✅ **易于管理** - 简单的Docker Compose命令

## 📞 技术支持

如果遇到问题，请检查：
1. Docker和Docker Compose是否正确安装
2. 端口8080是否被占用
3. 查看容器日志获取详细错误信息
4. 确保有足够的磁盘空间

现在您可以安全地使用预构建镜像部署系统了！