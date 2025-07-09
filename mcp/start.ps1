# Claude Memory MCP Server 启动脚本（Windows PowerShell版本）
# 
# 功能：
# - 使用相对路径启动 MCP Server
# - 自动检测项目ID
# - 检查必要的服务依赖
# - 支持跨项目共享部署

# 定位项目根目录
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
Set-Location $ProjectRoot

# 日志函数
function Write-Log {
    param($Message)
    $LogFile = Join-Path $ProjectRoot "logs\mcp_startup.log"
    $Timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -Path $LogFile -Value "[$Timestamp] $Message"
}

# 创建日志目录
$LogDir = Join-Path $ProjectRoot "logs"
if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir | Out-Null
}

# 自动检测项目ID
function Get-ProjectId {
    # 1. 优先读取 .claude.json
    $ClaudeJsonPath = Join-Path $ProjectRoot ".claude.json"
    if (Test-Path $ClaudeJsonPath) {
        try {
            $ClaudeJson = Get-Content $ClaudeJsonPath | ConvertFrom-Json
            if ($ClaudeJson.projectId -and $ClaudeJson.projectId -ne "{{ auto-detect }}") {
                Write-Log "Project ID from .claude.json: $($ClaudeJson.projectId)"
                return $ClaudeJson.projectId
            }
        } catch {
            Write-Log "Error reading .claude.json: $_"
        }
    }
    
    # 2. 使用当前目录名
    $CurrentDir = Split-Path -Leaf $ProjectRoot
    if ($CurrentDir) {
        Write-Log "Project ID from directory name: $CurrentDir"
        return $CurrentDir
    }
    
    # 3. 使用 git 仓库名称
    if (Test-Path (Join-Path $ProjectRoot ".git")) {
        try {
            $GitRemote = git remote get-url origin 2>$null
            if ($GitRemote) {
                $GitRepo = [System.IO.Path]::GetFileNameWithoutExtension($GitRemote)
                if ($GitRepo) {
                    Write-Log "Project ID from git repo: $GitRepo"
                    return $GitRepo
                }
            }
        } catch {
            Write-Log "Error getting git info: $_"
        }
    }
    
    # 4. 默认值
    Write-Log "Using default project ID: default"
    return "default"
}

# 检查 Python 虚拟环境
$VenvPath = Join-Path $ProjectRoot "venv"
if (-not (Test-Path $VenvPath)) {
    Write-Log "ERROR: Virtual environment not found at $VenvPath"
    Write-Host "Please run: python -m venv venv && venv\Scripts\Activate.ps1 && pip install -r requirements.txt" -ForegroundColor Red
    exit 1
}

# 激活虚拟环境
$ActivateScript = Join-Path $VenvPath "Scripts\Activate.ps1"
if (Test-Path $ActivateScript) {
    & $ActivateScript
    Write-Log "Virtual environment activated"
} else {
    Write-Log "ERROR: Cannot find activation script"
    exit 1
}

# 设置环境变量
$env:PYTHONPATH = "$ProjectRoot\src;$env:PYTHONPATH"
$env:PYTHONUNBUFFERED = "1"

# 设置项目ID
$env:CLAUDE_MEMORY_PROJECT_ID = Get-ProjectId
Write-Log "Using project ID: $env:CLAUDE_MEMORY_PROJECT_ID"

# 加载 .env 文件（如果存在）
$EnvFile = Join-Path $ProjectRoot ".env"
if (Test-Path $EnvFile) {
    Get-Content $EnvFile | ForEach-Object {
        if ($_ -match "^([^=]+)=(.*)$") {
            $name = $matches[1].Trim()
            $value = $matches[2].Trim()
            if ($name -and $value) {
                Set-Item -Path "env:$name" -Value $value
            }
        }
    }
    Write-Log "Loaded .env file"
}

# 检查必要的服务（异步）
Start-Job -ScriptBlock {
    param($ProjectRoot)
    
    function Write-Log {
        param($Message)
        $LogFile = Join-Path $ProjectRoot "logs\mcp_startup.log"
        $Timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
        Add-Content -Path $LogFile -Value "[$Timestamp] $Message"
    }
    
    # 检查 PostgreSQL
    $PostgresPort = if ($env:POSTGRES_PORT) { $env:POSTGRES_PORT } else { 5433 }
    try {
        $null = Test-NetConnection -ComputerName localhost -Port $PostgresPort -InformationLevel Quiet
        Write-Log "PostgreSQL is running"
    } catch {
        Write-Log "WARNING: PostgreSQL not running on port $PostgresPort"
        Write-Log "Memory persistence may not work properly"
    }
    
    # 检查 Qdrant
    $QdrantPort = if ($env:QDRANT_PORT) { $env:QDRANT_PORT } else { 6333 }
    try {
        $null = Test-NetConnection -ComputerName localhost -Port $QdrantPort -InformationLevel Quiet
        Write-Log "Qdrant is running"
    } catch {
        Write-Log "WARNING: Qdrant not running on port $QdrantPort"
        Write-Log "Semantic search may not work properly"
    }
} -ArgumentList $ProjectRoot | Out-Null

# 启动 MCP Server（stdio 模式）
Write-Log "Starting Claude Memory MCP Server for project: $env:CLAUDE_MEMORY_PROJECT_ID"
python -m claude_memory.mcp_server