#!/bin/bash

# ————— 配置部分 —————
WEBHOOK_URL="http://localhost:3009/send_private_msg"
MONITORED_CONTAINERS=("cloudflared_custom")  # 列出你要监控的容器名
RESTART_LIMIT=3       # 连续失败重启次数上限
PAUSE_AFTER_LIMIT=10800  # 达到上限后暂停多久（秒）= 3 小时 = 3*3600

STATE_DIR="/var/lib/docker-health-monitor"  # 存储状态、计数的目录
mkdir -p "$STATE_DIR"

# 针对 cloudflared 特殊检测
CLOUDFLARED_READY_URL="http://localhost:2000/metrics"

# ————— 通用函数 —————
send_webhook() {
    local message="$1"
    local escaped_message
    escaped_message=$(echo "$message" | sed 's/"/\\"/g')
    local payload="{ \"user_id\": 1647470402, \"message\": \"${escaped_message}\" }"
    curl -X POST "$WEBHOOK_URL" \
         -H "Authorization: xxx" \
         -H "Content-Type: application/json" \
                  -d "${payload}" >/dev/null 2>&1

    echo "WEBHOOK 发送通知: $message"
}

restart_container() {
    local cname="$1"
    docker restart "$cname"
}

# ————— 主逻辑 —————
for cname in "${MONITORED_CONTAINERS[@]}"; do
    # 状态文件路径
    count_file="$STATE_DIR/${cname}.count"
    last_fail_file="$STATE_DIR/${cname}.lastfail"

    # 读取当前失败计数
    if [ -f "$count_file" ]; then
        fail_count=$(cat "$count_file")
    else
        fail_count=0
    fi

    # 检测是否处于暂停状态
    if [ -f "$last_fail_file" ]; then
        last_fail=$(cat "$last_fail_file")
        now=$(date +%s)
        elapsed=$(( now - last_fail ))
        if [ "$elapsed" -lt "$PAUSE_AFTER_LIMIT" ]; then
            echo "$(date): $cname 在暂停重启阶段（上次重启失败 <3 h）"
            continue
        else
            # 过了恢复期，重置计数
            fail_count=0
            rm -f "$last_fail_file"
            echo "$(date): $cname 重启恢复期已过，重置失败计数"
        fi
    fi

    # 检查容器健康状态
    # 默认先用 docker inspect 来判断 health.status（如果定义有 HEALTHCHECK）
    health_status=$(docker inspect --format='{{.State.Health.Status}}' "$cname" 2>/dev/null)

    if [[ "$cname" == *cloudflared* ]]; then
        # 针对 cloudflared 做特殊检测（readiness endpoint）
        http_response=$(curl -s ${CLOUDFLARED_READY_URL} \
                     | grep -E '^cloudflared_tunnel_ha_connections [1-9]')
        if [ -z "$http_response" ]; then
            http_response="unhealthy"
        else
            http_response="healthy"
        fi
    fi
    echo "$(date): $cname readiness HTTP Response: $http_response"

    # 根据 health_status 决定是否重启
    if [ "$health_status" != "healthy" ]; then
        fail_count=$((fail_count + 1))
        echo "$(date): $cname 当前状态: $health_status，失败计数 = $fail_count"

        if [ "$fail_count" -gt "$RESTART_LIMIT" ]; then
            # 达到失败上限 → 记录失败时间，不再立即重启
            retry_limt_msg="$(date): $cname 重启失败次数已达上限，暂停重启 3 小时"
            echo ${retry_limt_msg}
            echo "$(( $(date +%s) ))" > "$last_fail_file"
            send_webhook ${retry_limt_msg}
        else
            # 执行重启
            echo "$(date): $cname 尝试重启容器"
            restart_container "$cname"
            send_webhook "容器 $cname 健康检测失败（状态: $health_status），正在重启。次数: $fail_count"
        fi

        # 保存当前失败计数
        echo "$fail_count" > "$count_file"

    else
        # 状态正常 → 重置失败计数
        if [ "$fail_count" -ne 0 ]; then
            echo "$(date): $cname 健康恢复，重置失败计数"
            fail_count=0
            echo "0" > "$count_file"
        fi
        echo "$(date): $cname 健康状态正常"
    fi
done
