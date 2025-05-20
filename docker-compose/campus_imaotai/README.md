# campus-imaotai Docker Compose 部署文档

## 目录结构

```shell
.
├── amaotai-docker-compose.yml         # docker-compose主配置文件
├── db/                        # MySQL初始化SQL文件目录（可选）
├── mysql_data/                # MySQL数据持久化目录
├── redis_data/                # Redis数据持久化目录
├── conf/                      # 后端配置文件目录（需放application-prod.yml）
├── jar/                       # 后端jar包目录（如campus-modular_xxx.jar）
├── html/                      # 前端dist静态文件目录
├── logs/                      # 应用日志目录
└── nginx.conf                 # Nginx主配置文件
```

## 环境要求

- Docker 版本 >= 20.10.0
- Docker Compose 版本 >= 2.0.0
- 服务器配置建议：
  - CPU: 2核心及以上
  - 内存: 4GB及以上
  - 磁盘空间: 20GB及以上
- 服务器需开放端口：
  - 80: 前端访问端口
  - 8160: 后端服务端口
  - 13306: MySQL端口（可选，用于远程访问）
  - 16379: Redis端口（可选，用于远程访问）

## 部署步骤

### 1. 准备工作

```bash
# 创建必要目录
mkdir -p db mysql_data redis_data conf jar html logs redis/conf

# 确保目录权限正确
chmod -R 755 .
chmod -R 777 logs
```

### 2. 配置文件准备

1. **数据库配置**
   - 将初始化SQL文件放入 `db/` 目录
   - SQL文件需包含数据库创建和表结构

2. **后端配置**
   - 在 `conf/` 目录下创建 `application-prod.yml`
   - 主要配置项：
     - 数据库连接信息
     - Redis连接信息
     - 文件上传路径
     - 日志配置
     - JWT配置

3. **前端文件**
   - 将打包后的dist目录内容复制到 `html/` 目录

4. **Nginx配置**
   - 配置前端静态文件路径
   - 配置API转发规则
   - 配置SSL证书（如需要）

### 3. 构建和部署

```bash
# 1. 构建前后端文件
docker-compose -f amaotai-docker-compose.yml up --build frontend-build backend-build

# 2. 启动所有服务
docker-compose -f amaotai-docker-compose.yml up -d

# 3. 检查服务状态
docker-compose -f amaotai-docker-compose.yml ps

# 4. 查看服务日志
docker-compose -f amaotai-docker-compose.yml logs -f
```

### 4. 服务管理命令

```bash
# 清理所有的未使用的缓存
docker system prune -a -f

# 停止所有服务
docker-compose -f amaotai-docker-compose.yml down

# 重启单个服务
docker-compose -f amaotai-docker-compose.yml restart [service_name]

# 查看指定服务日志
docker-compose -f amaotai-docker-compose.yml logs -f [service_name]

# 进入容器内部
docker-compose -f amaotai-docker-compose.yml exec [service_name] bash
```

## 问题排查指南

### 1. 服务启动问题

1. **MySQL启动失败**
   ```bash
   # 检查日志
   docker-compose -f amaotai-docker-compose.yml logs mysql
   
   # 常见解决方案：
   - 检查mysql_data目录权限
   - 确认端口13306未被占用
   - 检查配置文件中的用户名密码
   ```

2. **后端服务连接数据库失败**
   ```bash
   # 检查连接
   docker-compose -f amaotai-docker-compose.yml exec mysql mysql -uroot -p
   
   # 排查步骤：
   1. 确认MySQL服务已完全启动
   2. 检查application-prod.yml中的数据库配置
   3. 验证数据库用户权限
   ```

3. **Redis连接问题**
   ```bash
   # 测试Redis连接
   docker-compose -f amaotai-docker-compose.yml exec redis redis-cli ping
   
   # 排查步骤：
   1. 确认Redis服务状态
   2. 检查Redis配置信息
   3. 验证持久化目录权限
   ```

4. **Nginx配置问题**
   ```bash
   # 测试配置是否正确
   docker-compose -f amaotai-docker-compose.yml exec nginx nginx -t
   
   # 常见问题：
   - 静态文件路径错误
   - 反向代理配置有误
   - SSL证书配置问题
   ```

### 2. 性能优化建议

1. **MySQL优化**
   - 适当调整max_connections
   - 配置合理的innodb_buffer_pool_size
   - 启用慢查询日志分析

2. **Redis优化**
   - 启用持久化
   - 配置合理的maxmemory
   - 设置适当的淘汰策略

3. **JVM优化**
   - 调整堆内存大小
   - 配置GC参数
   - 启用JMX监控

### 3. 监控和维护

1. **日志管理**
   ```bash
   # 查看所有容器日志
   docker-compose -f amaotai-docker-compose.yml logs --tail=100
   
   # 清理日志文件
   find ./logs -name "*.log" -mtime +7 -delete
   ```

2. **数据备份**
   ```bash
   # MySQL备份
   docker-compose -f amaotai-docker-compose.yml exec mysql mysqldump -uroot -p campus_imaotai > backup.sql
   
   # Redis备份
   docker-compose -f amaotai-docker-compose.yml exec redis redis-cli save
   ```

## 安全建议

1. **端口安全**
   - 只对外开放必要端口
   - 使用防火墙限制访问来源

2. **数据安全**
   - 定期备份数据
   - 加密敏感信息
   - 设置强密码

3. **容器安全**
   - 定期更新镜像
   - 限制容器资源使用
   - 监控容器状态

## 参考资料
- [官方文档](https://oddfar.github.io/campus-doc/pages/8f2aa8/#%E5%90%AF%E5%8A%A8)
- [GitHub项目](https://github.com/oddfar/campus-imaotai)
- [Docker官方文档](https://docs.docker.com/)
- [Docker Compose文档](https://docs.docker.com/compose/)

## 问题反馈

如遇到问题，请：
1. 查看具体服务的日志
2. 检查配置文件
3. 参考问题排查指南
4. 提供详细的错误信息和环境信息

---
如有更多问题，欢迎在GitHub提交Issue！ 