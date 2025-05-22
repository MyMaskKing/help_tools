FROM n8nio/n8n:latest

# 设置时区为 Asia/Shanghai
ENV TZ=Asia/Shanghai
RUN apt-get update && \
    apt-get install -y tzdata && \
    ln -fs /usr/share/zoneinfo/Asia/Shanghai /etc/localtime && \
    dpkg-reconfigure -f noninteractive tzdata && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# 配置环境变量
ENV DB_TYPE=postgresdb \
    DB_POSTGRESDB_HOST=aws-0-us-west-1.pooler.supabase.com \
    DB_POSTGRESDB_PORT=5432 \
    DB_POSTGRESDB_DATABASE=postgres \
    DB_POSTGRESDB_USER=postgres.zjsypmcmtecsfvxzjhsb \
    DB_POSTGRESDB_PASSWORD=cyj123456 \
    N8N_BASIC_AUTH_ACTIVE=true \
    N8N_BASIC_AUTH_USER=admin \
    N8N_BASIC_AUTH_PASSWORD=cyj123456 \