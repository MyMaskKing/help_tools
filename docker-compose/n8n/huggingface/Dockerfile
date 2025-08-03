# 使用 PostgreSQL 作为基础镜像
FROM nikolaik/python-nodejs:python3.12-nodejs20

# 添加维护者信息
LABEL maintainer="ai来事 <https://www.youtube.com/@all.ai.>"

ARG CACHEBUST=222

# 设置构建参数，提供默认值
ARG WEBHOOK_URL=https://你的hf账户名-空间名.hf.space/
ARG POSTGRESDB_PORT=5432

# 设置基本环境变量
ENV WEBHOOK_URL=${WEBHOOK_URL} \
    N8N_HOST=0.0.0.0 \
    N8N_PORT=7860 \
    N8N_PROTOCOL=https \
    GENERIC_TIMEZONE=Asia/Shanghai \
    N8N_METRICS=true \
    QUEUE_HEALTH_CHECK_ACTIVE=true \
    N8N_PAYLOAD_SIZE_MAX=256 \
    DB_TYPE=postgresdb \
    DB_POSTGRESDB_PORT=${POSTGRESDB_PORT} \
    VIRTUAL_ENV=/home/pn/venv \
    PATH="/home/pn/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:$PATH" \
    # 添加 Qdrant 配置
    QDRANT_HOST=http://localhost \
    QDRANT_PORT=6333 \
    QDRANT_VERSION=1.12.4 \
    # 添加超时配置
    WAIT_TIMEOUT=30 \
    # 添加日志级别
    N8N_LOG_LEVEL=info \
    # 添加健康检查配置
    HEALTH_CHECK_INTERVAL=300

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    unzip \
    gnupg \
    build-essential \
    sudo \
    vim \
    git \
    procps \
    lsof \
    net-tools \
    ca-certificates \
    openssl \
    tzdata \
    htop \
    jq \
    netcat-openbsd \
    redis-server \
    && ln -fs /usr/share/zoneinfo/Asia/Shanghai /etc/localtime \
    && dpkg-reconfigure --frontend noninteractive tzdata \
    # 下载并安装预编译的 Qdrant
    && cd /tmp \
    && curl -L https://github.com/qdrant/qdrant/releases/download/v${QDRANT_VERSION}/qdrant-x86_64-unknown-linux-gnu.tar.gz -o qdrant.tar.gz \
    && tar xvf qdrant.tar.gz \
    && mv qdrant /usr/local/bin/ \
    && rm qdrant.tar.gz \
    # 创建 Qdrant 配置目录和数据目录
    && mkdir -p /home/pn/.n8n/qdrant/storage \
    && mkdir -p /home/pn/.n8n/qdrant/config \
    && mkdir -p /home/pn/.n8n/qdrant/snapshots \
    && chown -R pn:pn /home/pn/.n8n/qdrant \
    && chmod -R 755 /home/pn/.n8n/qdrant \
    # 清理
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    # 创建虚拟环境并安装 Python 依赖
    && python3 -m venv $VIRTUAL_ENV \
    && $VIRTUAL_ENV/bin/pip install --no-cache-dir --upgrade pip requests yt-dlp \
    # 安装 n8n
    && npm install -g n8n@latest pnpm \
    && npm list -g n8n \
    && npm cache clean --force

# 创建健康检查脚本
COPY --chown=pn:pn healthcheck.sh /home/pn/n8n/healthcheck.sh
RUN chmod +x /home/pn/n8n/healthcheck.sh

# 创建环境变量文件
RUN --mount=type=secret,id=POSTGRES_USER,mode=0444,required=true \
    --mount=type=secret,id=POSTGRES_PASSWORD,mode=0444,required=true \
    --mount=type=secret,id=POSTGRES_DB,mode=0444,required=true \
    --mount=type=secret,id=POSTGRESDB_HOST,mode=0444,required=true \
    echo "export DB_POSTGRESDB_HOST=$(cat /run/secrets/POSTGRESDB_HOST)" && \
    echo "export DB_POSTGRESDB_USER=$(cat /run/secrets/POSTGRES_USER)"  && \
    echo "export DB_POSTGRESDB_PASSWORD=$(cat /run/secrets/POSTGRES_PASSWORD)" && \
    echo "export DB_POSTGRESDB_DATABASE=$(cat /run/secrets/POSTGRES_DB)" && \
    echo "export DB_POSTGRESDB_HOST=$(cat /run/secrets/POSTGRESDB_HOST)" >> /home/pn/.env && \
    echo "export DB_POSTGRESDB_USER=$(cat /run/secrets/POSTGRES_USER)" >> /home/pn/.env && \
    echo "export DB_POSTGRESDB_PASSWORD=$(cat /run/secrets/POSTGRES_PASSWORD)" >> /home/pn/.env && \
    echo "export DB_POSTGRESDB_DATABASE=$(cat /run/secrets/POSTGRES_DB)" >> /home/pn/.env && \
    echo "export N8N_BASIC_AUTH_ACTIVE=true" >> /home/pn/.env && \
    echo "export N8N_BASIC_AUTH_USER=admin" >> /home/pn/.env && \
    echo "export N8N_BASIC_AUTH_PASSWORD=cyj123456" >> /home/pn/.env && \
    echo "export N8N_USER_MANAGEMENT_DISABLED=false" >> /home/pn/.env && \
    echo "export N8N_AUTH_EXCLUDE_ENDPOINTS=signup" >> /home/pn/.env && \
    echo "export N8N_LOG_LEVEL=debug" >> /home/pn/.env && \
    echo "export N8N_LOG_OUTPUT=console" >> /home/pn/.env && \
    echo "export N8N_AUTH_EXCLUDE_ENDPOINTS=signup,login" >> /home/pn/.env && \
    chown pn:pn /home/pn/.env

# 创建工作目录
WORKDIR /home/pn/n8n

# 复制启动脚本并创建数据目录
COPY --chown=pn:pn run.sh ./run.sh
COPY --chown=pn:pn config/n8n_env.sh ./config/n8n_env.sh
RUN chmod +x ./run.sh \
    && mkdir -p /home/pn/.n8n \
    && chown -R pn:pn /home/pn/.n8n \
    && chown -R pn:pn /home/pn/n8n

# 暴露端口
EXPOSE 7860

# 切换到非 root 用户
USER pn

# 设置数据卷
VOLUME ["/home/pn/.n8n"]

# 添加健康检查
HEALTHCHECK --interval=5m --timeout=3s \
  CMD curl -f http://localhost:7860/healthz || exit 1

# 启动命令
CMD ["./run.sh"]
