#!/bin/bash

# Webhook URL
WEBHOOK_URL="http://localhost:3009/send_private_msg"

# 定义 readiness endpoint
READY_URL="http://localhost:2000/ready"

# 方法：发送 webhook 通知
send_webhook() {
    local message="$1"
    # 构造 JSON 数据
    local payload
    # 转义 message 中的双引号等字符
    # 简单处理，替换双引号为 escaped 形式
    local escaped_message
    escaped_message=$(echo "$message" | sed 's/"/\\"/g')
    payload="{ \"user_id\": 1647470402, \"message\": \"${escaped_message}\" }"
    curl -X POST "$WEBHOOK_URL" \
         -H "Authorization: cyj123456" \
         -H "Content-Type: application/json" \
         -d "${payload}" >/dev/null 2>&1
    echo "WEBHOOK SEND OVER"
}

# 用 curl 检查 readiness endpoint
HTTP_INFO=$(curl -s --head --max-time 5 "$READY_URL" 2>&1)
HTTP_STATUS=$(echo "$HTTP_INFO" | grep -oP '(?<=HTTP/1\.[01] )\d{3}' | head -n1)
if [ -z "$HTTP_STATUS" ]; then
    HTTP_STATUS="NO_RESPONSE"
fi

if [ "$HTTP_STATUS" != "200" ]; then
    TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
    error_detail="$HTTP_INFO"
    message="cloudflared 隧道健康检查失败。状态码: $HTTP_STATUS；错误信息: $error_detail；已重启服务。时间: $TIMESTAMP"
    echo "$message"

    # 重启 cloudflared
    systemctl restart cloudflared

    # 发通知
    send_webhook "$message"
else
    echo "cloudflared 隧道健康状态码: $HTTP_STATUS"
fi
