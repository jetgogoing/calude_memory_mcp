# 部署目录说明

本目录包含 Claude Memory MCP Service 的所有部署相关文件。

## 目录结构

```
deploy/
├── docker/           # Docker 部署文件
│   ├── docker-compose.yml
│   └── Dockerfile
├── scripts/          # 部署和运维脚本
│   ├── start.sh     # 启动服务
│   ├── stop.sh      # 停止服务
│   ├── logs.sh      # 查看日志
│   ├── health-check.sh  # 健康检查
│   └── clean.sh     # 清理数据
└── k8s/             # Kubernetes 部署文件（待实现）
    ├── deployment.yaml
    ├── service.yaml
    └── configmap.yaml
```

## 快速开始

### Docker 部署

1. 进入部署目录：
   ```bash
   cd deploy/docker
   ```

2. 复制配置文件：
   ```bash
   cp ../../.env.minimal .env
   # 或使用其他配置模板
   ```

3. 启动服务：
   ```bash
   docker compose up -d
   ```

### 使用部署脚本

从项目根目录执行：

```bash
# 启动所有服务
./deploy/scripts/start.sh

# 查看日志
./deploy/scripts/logs.sh

# 停止服务
./deploy/scripts/stop.sh
```

## 部署方式

### 1. Docker Compose（推荐）
- 适用于：单机部署、开发测试
- 文件位置：`docker/`
- 特点：简单快速，一键启动

### 2. Kubernetes（计划中）
- 适用于：生产环境、集群部署
- 文件位置：`k8s/`
- 特点：高可用、自动伸缩

### 3. 云服务商部署（计划中）
- AWS ECS/EKS
- Google Cloud Run/GKE
- Azure Container Instances/AKS

## 环境配置

请参考项目根目录的配置文件：
- `.env.minimal` - 最小化配置
- `.env.development` - 开发环境
- `.env.production` - 生产环境

详细配置说明请查看 `/config/README.md`