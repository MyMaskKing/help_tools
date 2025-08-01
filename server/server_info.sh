#!/bin/bash
# 获取当前网络IP及谷歌连通性测试，并发送至 Webhook

# 检查并安装 jq（适用于 Ubuntu）
if ! command -v jq &>/dev/null; then
  echo "检测到未安装 jq，正在安装..."
  sudo apt-get update
  sudo apt-get install -y jq
  echo "✅ jq 安装完成：$(jq --version)"
else
  echo "✅ 已安装 jq：$(jq --version)"
fi

# 获取本机 IP
IP=$(ip -4 addr show "$(ip route get 1.1.1.1 | awk '/dev/ {print $5; exit}')" \
     | awk '/inet /{print $2}' | cut -d/ -f1)

# 检测 Google 可访问性
STATUS=$(curl -s --max-time 2 -I http://www.google.com | head -n1 | cut -d' ' -f2)
ACCESS="否"; [[ "$STATUS" =~ ^[23] ]] && ACCESS="可"

# 获取整体内存使用情况（单位 MB）
read total used <<< $(free -m | awk 'NR==2{print $2, $3}')
percent=$(awk "BEGIN {printf \"%.2f\", $used*100/$total}")

# 获取内存使用前10进程，并格式化
TOP10=$(ps aux --sort=-rss | head -n 11 | tail -n +2 | awk 'NR<=10{
    user=$1; pid=$2; mem=$4;
    rss_kb=$6;
    if (rss_kb>=1048576) {rss=sprintf("%.2fG",rss_kb/1048576)}
    else if (rss_kb>=1024) {rss=sprintf("%.2fM",rss_kb/1024)}
    else {rss=sprintf("%dK",rss_kb)};
    cmd="";
    for(i=11;i<=NF;i++){cmd=cmd $i " "}
    printf("%d\t%s\t%s\t%s\t%s\t%s\n", NR, user, pid, mem"%", rss, cmd)
}')

# 当前时间
TIMESTAMP=$(date +"%Y-%m-%d %H:%M:%S")

# 构建 HTML 内容
CONTENT=$(cat <<EOF
<!DOCTYPE html>
<html lang="zh-CN">
<body style="margin:0;padding:20px;font-family:Arial,sans-serif;background:#f0f0f0;">
  <table width="100%" cellpadding="0" cellspacing="0" role="presentation"
         style="max-width:600px;margin:auto;background:#fff;border-collapse:collapse;">
    <tr><td style="padding:20px;text-align:center;background:#007ACC;">
      <h1 style="color:#fff;margin:0;font-size:20px;">迷你主机当前信息</h1>
    </td></tr>
    <tr><td style="padding:20px;">
      <table width="100%" cellpadding="8" cellspacing="0" style="border-collapse:collapse;">
        <tr><th align="left" style="background:#f9f9f9;">时间</th><td>${TIMESTAMP}</td></tr>
        <tr><th align="left" style="background:#f9f9f9;">内网 IP</th><td>${IP}</td></tr>
        <tr><th align="left" style="background:#f9f9f9;">谷歌连通</th><td>${ACCESS}</td></tr>
      </table>

      <h3 style="margin-top:20px;color:#333;">内存使用前10的进程   <small>总体内存：${total} MB／已用：${used} MB（${percent} %）</small></h3>
      <table width="100%" cellpadding="6" cellspacing="0" role="presentation"
             style="border-collapse:collapse;">
        <tr style="background:#f9f9f9;">
          <th>编号</th><th>用户</th><th>PID</th><th>内存使用率</th><th>占用物理内存</th><th>命令</th>
        </tr>
        $(echo "$TOP10" | while IFS=$'\t' read -r no user pid mem rss cmd; do
            echo "<tr><td>${no}</td><td>${user}</td><td>${pid}</td><td>${mem}</td><td>${rss}</td><td>${cmd}</td></tr>"
        done)
      </table>
    </td></tr>
    <tr><td style="padding:10px;text-align:center;font-size:12px;color:#888;">
      © 2025 迷你主机监控
    </td></tr>
  </table>
</body>
</html>
EOF
)

# 终端输出
echo "===== 执行结果 ====="
echo "时间：${TIMESTAMP}"
echo "内网 IP：${IP}"
echo "谷歌连通：${ACCESS}"
echo "整体内存使用：${used} MB / ${total} MB (${percent} %)"

# POST JSON 到 Webhook
JSON=$(jq -n \
  --arg subject "迷你主机当前信息" \
  --arg content "$CONTENT" \
  --arg to "1647470402@qq.com" \
  '{subject: $subject, content: $content, to: $to}')
curl -s -X POST https://hook.us2.make.com/24p5furxx1t0socaodlqoa1pyr483air \
  -H "Content-Type: application/json" \
  -d "$JSON" && echo "🚀 已发送至 Webhook！"
