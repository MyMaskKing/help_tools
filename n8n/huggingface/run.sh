#!/bin/bash
set -eo pipefail

# 导入环境变量
source /home/pn/.env

# 错误处理函数
handle_error() {
    echo "错误发生在第 $1 行"
    exit 1
}
trap 'handle_error $LINENO' ERR

# 超时处理函数
timeout_handler() {
    echo "操作超时"
    exit 1
}

# 等待服务就绪的通用函数
wait_for_service() {
    local service=$1
    local host=$2
    local port=$3
    local timeout=${4:-$WAIT_TIMEOUT}
    
    echo "等待 $service 就绪..."
    local end=$((SECONDS + timeout))
    
    while [ $SECONDS -lt $end ]; do
        if nc -z "$host" "$port" >/dev/null 2>&1; then
            echo "$service 已就绪"
            return 0
        fi
        echo "尝试连接 $service at $host:$port..."
        sleep 1
    done
    
    echo "$service 启动超时"
    exit 1
}

# 启动 Redis 服务
start_redis() {
    echo "Starting Redis server..."
    redis-server --daemonize yes
    sleep 1
    if ! redis-cli ping > /dev/null 2>&1; then
        echo "Failed to start Redis server"
        exit 1
    fi
    
    # 设置 Redis 配置
    redis-cli config set maxmemory 512mb
    redis-cli config set maxmemory-policy allkeys-lru
    echo ""
    echo "Redis server started successfully"
    echo ""
}

# 启动 Qdrant 服务
start_qdrant() {
    echo "Starting Qdrant server..."
    
    # 确保目录存在并有正确的权限
    mkdir -p /home/pn/.n8n/qdrant/storage
    mkdir -p /home/pn/.n8n/qdrant/config
    mkdir -p /home/pn/.n8n/qdrant/snapshots
    mkdir -p /home/pn/.n8n/qdrant/logs
    
    # 设置正确的权限
    chmod -R 755 /home/pn/.n8n/qdrant
    chown -R pn:pn /home/pn/.n8n/qdrant
    
    # 创建 Qdrant 配置文件
    cat > /home/pn/.n8n/qdrant/config/config.yaml <<EOF
service:
  host: 0.0.0.0
  http_port: 6333
  grpc_port: 6334
  enable_cors: true
  enable_tls: false
  max_request_size_mb: 64
  max_workers: 0

storage:
  storage_path: /home/pn/.n8n/qdrant/storage
  snapshots_path: /home/pn/.n8n/qdrant/snapshots
  on_disk_payload: true
  
  performance:
    max_search_threads: 0
    max_optimization_threads: 0
    
  optimizers:
    deleted_threshold: 0.2
    vacuum_min_vector_number: 1000
    default_segment_number: 0
    max_segment_size_kb: null
    indexing_threshold_kb: 20000
    flush_interval_sec: 5
    
  hnsw_index:
    m: 16
    ef_construct: 100
    full_scan_threshold_kb: 10000
    max_indexing_threads: 0
    on_disk: false

logger:
  on_disk:
    enabled: true
    log_file: /home/pn/.n8n/qdrant/logs/qdrant.log
    log_level: INFO

telemetry_disabled: true
EOF

    # 确保配置文件有正确的权限
    chmod 644 /home/pn/.n8n/qdrant/config/config.yaml
    
    # 使用配置文件启动 Qdrant
    qdrant --config-path /home/pn/.n8n/qdrant/config/config.yaml > /home/pn/.n8n/qdrant/logs/startup.log 2>&1 &
    
    # 等待 Qdrant 启动
    local timeout=30
    local end=$((SECONDS + timeout))
    
    while [ $SECONDS -lt $end ]; do
        if curl -s http://localhost:6333/health >/dev/null; then
            echo "Qdrant server started successfully"
            
            # 预创建常用集合
            echo "Creating default collections..."
            
            # 创建文本向量集合 (768维，适用于多数文本嵌入模型)
            curl -X PUT 'http://localhost:6333/collections/text_vectors' \
                -H 'Content-Type: application/json' \
                -d '{
                    "vectors": {
                        "size": 768,
                        "distance": "Cosine",
                        "on_disk": true
                    },
                    "optimizers_config": {
                        "default_segment_number": 2,
                        "indexing_threshold": 20000,
                        "memmap_threshold": 10000
                    },
                    "hnsw_config": {
                        "m": 16,
                        "ef_construct": 100,
                        "full_scan_threshold": 10000,
                        "max_indexing_threads": 0,
                        "on_disk": true
                    },
                    "init_from": {
                        "collection_name": "text_vectors"
                    }
                }'
            
            # 创建图像向量集合 (512维，适用于多数图像嵌入模型)
            curl -X PUT 'http://localhost:6333/collections/image_vectors' \
                -H 'Content-Type: application/json' \
                -d '{
                    "vectors": {
                        "size": 512,
                        "distance": "Cosine"
                    },
                    "optimizers_config": {
                        "default_segment_number": 2,
                        "indexing_threshold": 20000
                    },
                    "hnsw_config": {
                        "m": 16,
                        "ef_construct": 100,
                        "full_scan_threshold": 10000
                    }
                }'
            
            # 创建通用向量集合 (1536维，适用于 OpenAI 的嵌入模型)
            curl -X PUT 'http://localhost:6333/collections/openai_vectors' \
                -H 'Content-Type: application/json' \
                -d '{
                    "vectors": {
                        "size": 1536,
                        "distance": "Cosine"
                    },
                    "optimizers_config": {
                        "default_segment_number": 2,
                        "indexing_threshold": 20000
                    },
                    "hnsw_config": {
                        "m": 16,
                        "ef_construct": 100,
                        "full_scan_threshold": 10000
                    }
                }'
                
            # 验证集合创建状态并输出详细信息
            echo -e "\nVerifying collections:"
            curl -s 'http://localhost:6333/collections' | jq '.'
            
            # 测试连接
            echo -e "\nTesting Qdrant connection:"
            curl -v http://localhost:6333/health
            
            return 0
        fi
        echo "Waiting for Qdrant to start..."
        sleep 1
        
        # 检查是否有错误日志
        if grep -i "error" /home/pn/.n8n/qdrant/logs/startup.log >/dev/null 2>&1; then
            echo "Error found in Qdrant logs:"
            tail -n 10 /home/pn/.n8n/qdrant/logs/startup.log
        fi
    done
    
    echo "Failed to start Qdrant server"
    echo "Last 10 lines of Qdrant log:"
    tail -n 10 /home/pn/.n8n/qdrant/logs/startup.log
    exit 1
}

# 检查服务状态
check_services() {
    echo "检查服务状态..."
    
    # 检查 Redis
    echo "Redis 状态："
    redis-cli info | grep 'used_memory\|connected_clients\|total_connections_received'
       
    # 检查 Qdrant
    echo "Qdrant 状态："
    if curl -s http://localhost:6333/metrics >/dev/null; then
        echo "Qdrant 运行正常"
        curl -s http://localhost:6333/metrics
        
        # 显示集合信息
        echo "Qdrant 集合列表："
        curl -s http://localhost:6333/collections
    else
        echo "Qdrant 服务异常"
        tail -n 10 /home/pn/.n8n/qdrant/qdrant.log
    fi
}

# 主流程
main() {
    current_time=$(date +"%Y-%m-%d %H:%M:%S")
    echo "Starting services at $current_time"
    
    # 输出配置信息
    echo "Database Configuration:"
    echo "Host: ${DB_POSTGRESDB_HOST}"
    echo "Port: ${DB_POSTGRESDB_PORT}"
    echo "User: ${DB_POSTGRESDB_USER}"
    echo "Database: ${DB_POSTGRESDB_DATABASE}"
    echo "Type: ${DB_TYPE}"
    
    # 启动服务
    wait_for_service "PostgreSQL" "${DB_POSTGRESDB_HOST}" "${DB_POSTGRESDB_PORT}"
    echo ""
    start_redis
    echo ""
    start_qdrant
    echo ""
    check_services
    
    # 设置 N8N 环境变量
    source /home/pn/n8n/config/n8n_env.sh
    
    echo ""
    echo "Starting n8n..."
    
    # 启动健康检查（后台运行）
    ./healthcheck.sh &
    HEALTH_CHECK_PID=$!
    
    # 启动n8n
    exec n8n start
    
    # 如果n8n退出，也停止健康检查
    kill $HEALTH_CHECK_PID 2>/dev/null
}

# 执行主流程
main "$@"
