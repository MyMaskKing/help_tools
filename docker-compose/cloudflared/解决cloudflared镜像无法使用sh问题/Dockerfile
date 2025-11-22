# Dockerfile
# ------------------------------------------------------------
# 🎯 关键修正：使用您已成功拉取的标签
FROM alpine:latest 

# 阶段 1：构建环境
# 安装 curl 和 grep 工具。这些是健康检查脚本（curl | grep）所必需的。
RUN apk update && apk add --no-cache curl grep

# 阶段 2：从官方 cloudflared 镜像中复制可执行文件。
COPY --from=cloudflare/cloudflared:latest /usr/local/bin/cloudflared /usr/local/bin/cloudflared

# 设置容器启动时执行的入口点
ENTRYPOINT ["/usr/local/bin/cloudflared"]
# ------------------------------------------------------------