#!/bin/bash

# 配置
SUB_DIR="$HOME/agsb/sub"
PYTHON_VENV="$SUB_DIR/venv"
LOG_FILE="$SUB_DIR/manage.log"
PID_FILE="$SUB_DIR/sub_server.pid"

# 日志函数
log() {
    local level=$1
    local message=$2
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[$timestamp] [$level] $message" | tee -a "$LOG_FILE"
}

# 检查依赖
check_dependencies() {
    command -v python3 >/dev/null 2>&1 || { log "ERROR" "需要Python3但未安装"; exit 1; }
    command -v pip3 >/dev/null 2>&1 || { log "ERROR" "需要pip3但未安装"; exit 1; }
}

# 初始化Python虚拟环境
init_venv() {
    if [ ! -d "$PYTHON_VENV" ]; then
        log "INFO" "创建Python虚拟环境"
        python3 -m venv "$PYTHON_VENV"
    fi
    
    source "$PYTHON_VENV/bin/activate"
    pip install flask gunicorn
}

# 启动订阅服务器
start_server() {
    if [ -f "$PID_FILE" ]; then
        local pid
        pid=$(cat "$PID_FILE")
        if kill -0 "$pid" 2>/dev/null; then
            log "INFO" "服务器已在运行 (PID: $pid)"
            return 0
        fi
    fi
    
    source "$PYTHON_VENV/bin/activate"
    
    log "INFO" "启动订阅服务器"
    nohup gunicorn -w 4 -b 0.0.0.0:8080 sub_server:app > "$SUB_DIR/server.log" 2>&1 &
    echo $! > "$PID_FILE"
    
    # 等待服务器启动
    sleep 2
    if curl -s http://localhost:8080/sub/status >/dev/null; then
        log "INFO" "服务器启动成功"
    else
        log "ERROR" "服务器启动失败"
        return 1
    fi
}

# 停止订阅服务器
stop_server() {
    if [ -f "$PID_FILE" ]; then
        local pid
        pid=$(cat "$PID_FILE")
        if kill -0 "$pid" 2>/dev/null; then
            kill "$pid"
            rm "$PID_FILE"
            log "INFO" "服务器已停止"
        else
            log "WARN" "服务器未运行"
        fi
    else
        log "WARN" "PID文件不存在"
    fi
}

# 重启订阅服务器
restart_server() {
    stop_server
    sleep 2
    start_server
}

# 主函数
main() {
    local action=$1
    shift
    
    case "$action" in
        "init")
            check_dependencies
            init_venv
            ;;
        "start")
            start_server
            ;;
        "stop")
            stop_server
            ;;
        "restart")
            restart_server
            ;;
        *)
            echo "Usage: $0 {init|start|stop|restart}"
            exit 1
            ;;
    esac
}

main "$@" 