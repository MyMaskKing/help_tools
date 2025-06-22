#!/bin/bash

# 获取健康检查间隔时间（默认1800秒，30分钟）
INTERVAL=${HEALTH_CHECK_INTERVAL:-1800}

# 登录凭证
AUTH_USER=${N8N_BASIC_AUTH_USER:-admin}
AUTH_PASS=${N8N_BASIC_AUTH_PASSWORD:-cyj123456}

# 日志文件
LOG_DIR="/home/pn/.n8n/logs"
LOG_FILE="${LOG_DIR}/healthcheck.log"

# 确保日志目录存在
mkdir -p "$LOG_DIR"
touch "$LOG_FILE"
chmod 644 "$LOG_FILE"

# 日志函数
log() {
    local level=$1
    local message=$2
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[$timestamp] [$level] $message" | tee -a "$LOG_FILE"
}

# 检查n8n服务
check_n8n() {
    local response=$(curl -s -w "%{http_code}" -o /dev/null \
        -u "${AUTH_USER}:${AUTH_PASS}" \
        "http://localhost:${N8N_PORT:-7860}/healthz")

    if [ "$response" = "200" ]; then
        log "INFO" "n8n健康检查成功"
        return 0
    else
        log "WARN" "n8n健康检查失败，HTTP状态码: $response"
        # 尝试访问主页面以保持活跃
        curl -s -f -u "${AUTH_USER}:${AUTH_PASS}" \
            "http://localhost:${N8N_PORT:-7860}/" > /dev/null
        return 1
    fi
}

# 检查Redis服务
check_redis() {
    if ! redis-cli ping > /dev/null 2>&1; then
        log "ERROR" "Redis服务异常，尝试重启"
        redis-server --daemonize yes
        return 1
    fi
    log "INFO" "Redis服务正常"
    return 0
}

# 检查Qdrant服务
check_qdrant() {
    if ! curl -s http://localhost:6333/health > /dev/null; then
        log "ERROR" "Qdrant服务异常"
        return 1
    fi
    log "INFO" "Qdrant服务正常"
    return 0
}

log "INFO" "健康检查服务启动 - 间隔: ${INTERVAL}秒"

# 主循环
while true; do
    # 检查所有服务
    check_n8n
    check_redis
    check_qdrant
    
    # 清理旧日志（保留最近7天）
    find "$LOG_DIR" -name "*.log" -type f -mtime +7 -delete
    
    # 等待指定时间后再次检查
    sleep $INTERVAL
done 