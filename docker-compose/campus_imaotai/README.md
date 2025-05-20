# campus-imaotai Docker Compose 部署文档

## 目录结构

```shell
.
├── campus_imaotai.yml         # docker-compose主配置文件
├── db/                        # MySQL初始化SQL文件目录（可选）
├── mysql_data/                # MySQL数据持久化目录
├── redis_data/                # Redis数据持久化目录
├── conf/                      # 后端配置文件目录（需放application-prod.yml）
├── jar/                       # 后端jar包目录（如campus-modular_xxx.jar）
├── html/                      # 前端dist静态文件目录
└── nginx.conf                 # Nginx主配置文件
```

## 环境准备

- 安装 [Docker](https://docs.docker.com/get-docker/)
- 安装 [Docker Compose](https://docs.docker.com/compose/install/)
- 服务器需开放 80、8160、13306、16379 端口（如需远程访问）

## 配置说明

1. **数据库初始化**
   - `db/` 目录下可放置初始化SQL文件，首次启动时自动导入。
2. **MySQL数据**
   - `mysql_data/` 用于持久化数据库数据。
3. **Redis数据**
   - `redis_data/` 用于持久化Redis缓存数据。
4. **后端配置**
   - `conf/` 目录下需放置 `application-prod.yml`，配置数据库、Redis等连接信息。
5. **后端jar包**
   - `jar/` 目录下放置 `campus-modular_xxx.jar`。
6. **前端静态文件**
   - `html/` 目录下放置前端打包后的 `dist` 文件夹内容。
7. **Nginx配置**
   - `nginx.conf` 需根据实际前后端路径和API代理规则调整。

## 启动服务

```shell
# 启动所有服务
sudo docker-compose -f campus_imaotai.yml up -d

# 查看服务状态
sudo docker-compose -f campus_imaotai.yml ps

# 查看日志（如需排查问题）
sudo docker-compose -f campus_imaotai.yml logs -f

# 停止所有服务
sudo docker-compose -f campus_imaotai.yml down

# 重启服务
sudo docker-compose -f campus_imaotai.yml restart
```

## 常见问题

1. **端口冲突**
   - 如本地已占用13306、16379、8160、80端口，请在yml文件中自行修改。
2. **数据库初始化失败**
   - 检查 `db/` 目录下SQL文件是否正确，或手动导入SQL。
3. **后端无法连接数据库/Redis**
   - 检查 `application-prod.yml` 配置，确保host、端口、用户名、密码正确。
4. **前端页面无法访问或接口404**
   - 检查 `nginx.conf` 配置，确保代理规则正确。
5. **数据丢失**
   - 请勿随意删除 `mysql_data/`、`redis_data/` 目录。

## 参考资料
- [官方文档](https://oddfar.github.io/campus-doc/pages/8f2aa8/#%E5%90%AF%E5%8A%A8)
- [GitHub项目](https://github.com/oddfar/campus-imaotai)

---
如有更多问题，欢迎反馈！ 