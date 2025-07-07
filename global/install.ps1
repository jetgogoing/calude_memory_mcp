# Claude Memory MCP 全局服务 Windows 安装脚本
# PowerShell 版本，支持Windows环境一键部署

param(
    [switch]$Auto = $false,
    [switch]$SkipBuild = $false,
    [switch]$Help = $false
)

$Version = "2.0.0"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$LogFile = "$env:TEMP\claude_memory_install.log"

# 颜色函数
function Write-ColorOutput {
    param([string]$Message, [string]$Color = "White")
    
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $logMessage = "[$timestamp] $Message"
    
    switch ($Color) {
        "Green" { Write-Host $logMessage -ForegroundColor Green }
        "Red" { Write-Host $logMessage -ForegroundColor Red }
        "Yellow" { Write-Host $logMessage -ForegroundColor Yellow }
        "Blue" { Write-Host $logMessage -ForegroundColor Blue }
        "Cyan" { Write-Host $logMessage -ForegroundColor Cyan }
        default { Write-Host $logMessage }
    }
    
    Add-Content -Path $LogFile -Value $logMessage
}

function Show-Banner {
    Write-Host @"
╔═══════════════════════════════════════════════════════════════╗
║                                                               ║
║               Claude Memory MCP 全局服务                       ║
║                                                               ║
║           🧠 跨项目智能记忆管理系统 v2.0.0                     ║
║                                                               ║
║   ✨ 零配置部署 | 🔄 自动迁移 | 🌐 全局共享 | 🚀 即插即用        ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
"@ -ForegroundColor Magenta
}

function Show-Help {
    Write-Host @"
Claude Memory MCP 全局服务 Windows 安装器

用法: .\install.ps1 [参数]

参数:
  -Auto        自动模式，跳过交互式配置
  -SkipBuild   跳过Docker镜像构建
  -Help        显示此帮助信息

示例:
  .\install.ps1              # 交互式安装
  .\install.ps1 -Auto        # 自动安装
  .\install.ps1 -Auto -SkipBuild  # 自动安装，跳过构建

要求:
  - Windows 10/11 或 Windows Server 2019+
  - Docker Desktop for Windows
  - PowerShell 5.1+ 或 PowerShell Core 7+
  - 至少2GB可用磁盘空间

"@
}

function Test-Dependencies {
    Write-ColorOutput "检查系统依赖..." "Blue"
    
    $missing = @()
    
    # 检查Docker
    try {
        $dockerVersion = docker --version 2>$null
        if ($dockerVersion) {
            Write-ColorOutput "✓ Docker已安装: $dockerVersion" "Green"
        } else {
            $missing += "Docker"
        }
    } catch {
        $missing += "Docker"
    }
    
    # 检查Docker Compose
    try {
        $composeVersion = docker-compose --version 2>$null
        if ($composeVersion) {
            Write-ColorOutput "✓ Docker Compose已安装: $composeVersion" "Green"
        } else {
            # 尝试Docker Compose v2
            $composeV2 = docker compose version 2>$null
            if ($composeV2) {
                Write-ColorOutput "✓ Docker Compose v2已安装" "Green"
            } else {
                $missing += "Docker Compose"
            }
        }
    } catch {
        $missing += "Docker Compose"
    }
    
    # 检查Git (可选)
    try {
        $gitVersion = git --version 2>$null
        if ($gitVersion) {
            Write-ColorOutput "✓ Git已安装: $gitVersion" "Green"
        }
    } catch {
        Write-ColorOutput "⚠ Git未安装(可选)" "Yellow"
    }
    
    if ($missing.Count -gt 0) {
        Write-ColorOutput "缺少必要依赖: $($missing -join ', ')" "Red"
        Write-Host ""
        Write-Host "请安装以下依赖后重新运行:" -ForegroundColor Yellow
        Write-Host ""
        
        foreach ($dep in $missing) {
            switch ($dep) {
                "Docker" {
                    Write-Host "  Docker Desktop: https://www.docker.com/products/docker-desktop" -ForegroundColor Cyan
                    Write-Host "  或使用winget: winget install Docker.DockerDesktop" -ForegroundColor Cyan
                }
                "Docker Compose" {
                    Write-Host "  Docker Compose通常随Docker Desktop安装" -ForegroundColor Cyan
                    Write-Host "  或手动安装: https://docs.docker.com/compose/install/" -ForegroundColor Cyan
                }
            }
        }
        
        exit 1
    }
    
    Write-ColorOutput "✓ 所有依赖检查通过" "Green"
}

function Test-ClaudeCLI {
    Write-ColorOutput "检查Claude CLI..." "Blue"
    
    try {
        $claudeVersion = claude --version 2>$null
        if ($claudeVersion) {
            Write-ColorOutput "✓ Claude CLI已安装: $claudeVersion" "Green"
            
            # 检查配置目录
            $claudeConfigDir = "$env:APPDATA\claude"
            if (Test-Path "$claudeConfigDir\claude.json") {
                Write-ColorOutput "✓ Claude CLI配置文件存在" "Green"
                $script:ClaudeCLIReady = $true
            } else {
                Write-ColorOutput "Claude CLI配置文件不存在，将创建默认配置" "Yellow"
                $script:ClaudeCLIReady = $false
            }
        } else {
            throw "Claude CLI未找到"
        }
    } catch {
        Write-ColorOutput "Claude CLI未安装" "Yellow"
        Write-Host ""
        Write-Host "请先安装Claude CLI:" -ForegroundColor Yellow
        Write-Host "  npm install -g @anthropic/claude-cli" -ForegroundColor Cyan
        Write-Host "  或访问: https://docs.anthropic.com/claude/docs/claude-cli" -ForegroundColor Cyan
        Write-Host ""
        
        $continue = Read-Host "是否继续安装(Claude CLI将稍后配置)? [y/N]"
        if ($continue -notmatch '^[Yy]$') {
            exit 1
        }
        $script:ClaudeCLIReady = $false
    }
}

function New-GlobalDirectories {
    Write-ColorOutput "创建全局数据目录..." "Blue"
    
    $globalDataDir = "$env:USERPROFILE\.claude-memory"
    $script:GlobalDataDir = $globalDataDir
    
    $directories = @(
        "data", "logs", "config", "cache", "postgres", "qdrant"
    )
    
    foreach ($dir in $directories) {
        $fullPath = Join-Path $globalDataDir $dir
        if (!(Test-Path $fullPath)) {
            New-Item -ItemType Directory -Path $fullPath -Force | Out-Null
        }
    }
    
    Write-ColorOutput "✓ 全局数据目录创建完成: $globalDataDir" "Green"
    
    # 复制默认配置文件
    $configSource = Join-Path $ScriptDir "config\global_config.yml"
    $configDest = Join-Path $globalDataDir "config\global_config.yml"
    
    if (!(Test-Path $configDest) -and (Test-Path $configSource)) {
        Copy-Item $configSource $configDest
        Write-ColorOutput "✓ 默认配置文件已创建" "Green"
    }
}

function Build-DockerImages {
    Write-ColorOutput "构建Claude Memory全局Docker镜像..." "Blue"
    
    Push-Location $ScriptDir
    
    try {
        Write-ColorOutput "构建全局MCP服务镜像..." "Blue"
        $buildOutput = docker build -f Dockerfile.global -t claude-memory-global:$Version . 2>&1
        
        if ($LASTEXITCODE -eq 0) {
            Write-ColorOutput "✓ Docker镜像构建完成" "Green"
        } else {
            Write-ColorOutput "Docker镜像构建失败: $buildOutput" "Red"
            exit 1
        }
    } finally {
        Pop-Location
    }
}

function Start-Services {
    Write-ColorOutput "启动Claude Memory全局服务..." "Blue"
    
    Push-Location $ScriptDir
    
    try {
        # 检查并停止现有服务
        $existingServices = docker-compose -f docker-compose.global.yml ps -q 2>$null
        if ($existingServices) {
            Write-ColorOutput "停止现有服务..." "Blue"
            docker-compose -f docker-compose.global.yml down | Out-Null
        }
        
        # 启动服务
        Write-ColorOutput "启动全局服务栈..." "Blue"
        $startOutput = docker-compose -f docker-compose.global.yml up -d 2>&1
        
        if ($LASTEXITCODE -eq 0) {
            Write-ColorOutput "✓ 服务启动完成" "Green"
        } else {
            Write-ColorOutput "服务启动失败: $startOutput" "Red"
            Write-ColorOutput "查看详细日志: docker-compose -f docker-compose.global.yml logs" "Yellow"
            exit 1
        }
        
        # 等待服务就绪
        Write-ColorOutput "等待服务就绪..." "Blue"
        Start-Sleep -Seconds 10
        
        # 检查健康状态
        $maxAttempts = 30
        $attempt = 1
        
        while ($attempt -le $maxAttempts) {
            try {
                $healthCheck = docker exec claude-memory-global python /app/healthcheck.py 2>$null
                if ($LASTEXITCODE -eq 0) {
                    Write-ColorOutput "✓ 服务健康检查通过" "Green"
                    break
                }
            } catch {
                # 继续尝试
            }
            
            Write-ColorOutput "等待服务就绪... ($attempt/$maxAttempts)" "Blue"
            Start-Sleep -Seconds 5
            $attempt++
        }
        
        if ($attempt -gt $maxAttempts) {
            Write-ColorOutput "服务健康检查超时，但服务可能仍在初始化中" "Yellow"
        }
    } finally {
        Pop-Location
    }
}

function Set-ClaudeCLIConfig {
    Write-ColorOutput "配置Claude CLI集成..." "Blue"
    
    if (!$script:ClaudeCLIReady) {
        Write-ColorOutput "跳过Claude CLI配置(CLI未就绪)" "Yellow"
        return
    }
    
    $claudeConfigDir = "$env:APPDATA\claude"
    $claudeConfigFile = "$claudeConfigDir\claude.json"
    
    # 备份现有配置
    if (Test-Path $claudeConfigFile) {
        $backupFile = "$claudeConfigFile.backup.$(Get-Date -Format 'yyyyMMdd_HHmmss')"
        Copy-Item $claudeConfigFile $backupFile
        Write-ColorOutput "✓ 现有配置已备份到: $backupFile" "Green"
    }
    
    # 创建配置目录
    if (!(Test-Path $claudeConfigDir)) {
        New-Item -ItemType Directory -Path $claudeConfigDir -Force | Out-Null
    }
    
    # 生成配置
    $config = @{
        mcpServers = @{
            "claude-memory-global" = @{
                command = "docker"
                args = @("exec", "-i", "claude-memory-global", "python", "/app/global_mcp_server.py")
                env = @{}
            }
        }
    }
    
    $configJson = $config | ConvertTo-Json -Depth 10
    Set-Content -Path $claudeConfigFile -Value $configJson -Encoding UTF8
    
    Write-ColorOutput "✓ Claude CLI MCP配置已更新" "Green"
}

function Test-Installation {
    Write-ColorOutput "验证安装..." "Blue"
    
    # 检查容器状态
    $containerStatus = docker ps --filter "name=claude-memory-global" --format "table {{.Names}}\t{{.Status}}" 2>$null
    if ($containerStatus -match "claude-memory-global") {
        Write-ColorOutput "✓ 全局MCP服务容器正在运行" "Green"
    } else {
        Write-ColorOutput "全局MCP服务容器未运行" "Red"
        return $false
    }
    
    # 检查健康状态
    try {
        $healthOutput = docker exec claude-memory-global python /app/healthcheck.py 2>$null
        if ($LASTEXITCODE -eq 0 -and $healthOutput -match '"overall_status": "ok"') {
            Write-ColorOutput "✓ 健康检查通过" "Green"
        } else {
            Write-ColorOutput "健康检查未通过，服务可能仍在初始化" "Yellow"
        }
    } catch {
        Write-ColorOutput "健康检查执行失败" "Yellow"
    }
    
    Write-ColorOutput "✓ 安装验证完成" "Green"
    return $true
}

function Show-Results {
    Write-Host ""
    Write-Host "╔═══════════════════════════════════════════════════════════════╗" -ForegroundColor Green
    Write-Host "║                                                               ║" -ForegroundColor Green
    Write-Host "║                  🎉 安装成功完成! 🎉                          ║" -ForegroundColor Green
    Write-Host "║                                                               ║" -ForegroundColor Green
    Write-Host "╚═══════════════════════════════════════════════════════════════╝" -ForegroundColor Green
    Write-Host ""
    
    Write-Host "📋 服务信息:" -ForegroundColor Cyan
    Write-Host "  🔗 MCP服务地址: localhost:6334"
    Write-Host "  📁 全局数据目录: $script:GlobalDataDir"
    Write-Host "  🐳 Docker容器: claude-memory-global"
    Write-Host "  📊 Vector数据库: localhost:6335"
    Write-Host ""
    
    Write-Host "🚀 快速开始:" -ForegroundColor Cyan
    Write-Host "  1. 打开PowerShell或命令提示符"
    Write-Host "  2. 运行Claude CLI"
    Write-Host "  3. 使用命令: " -NoNewline
    Write-Host "claude mcp call claude-memory-global memory_search" -ForegroundColor Green
    Write-Host ""
    
    Write-Host "🛠️  管理命令:" -ForegroundColor Cyan
    Write-Host "  启动服务: " -NoNewline
    Write-Host "docker-compose -f $ScriptDir\docker-compose.global.yml up -d" -ForegroundColor Green
    Write-Host "  停止服务: " -NoNewline
    Write-Host "docker-compose -f $ScriptDir\docker-compose.global.yml down" -ForegroundColor Green
    Write-Host "  查看日志: " -NoNewline
    Write-Host "docker logs claude-memory-global" -ForegroundColor Green
    Write-Host ""
    
    Write-Host "📖 可用MCP工具:" -ForegroundColor Cyan
    Write-Host "  • " -NoNewline
    Write-Host "memory_search" -ForegroundColor Green -NoNewline
    Write-Host "        - 搜索全局对话记忆"
    Write-Host "  • " -NoNewline
    Write-Host "get_recent_conversations" -ForegroundColor Green -NoNewline
    Write-Host " - 获取最近对话"
    Write-Host "  • " -NoNewline
    Write-Host "memory_status" -ForegroundColor Green -NoNewline
    Write-Host "        - 系统状态信息"
    Write-Host ""
    
    if (!$script:ClaudeCLIReady) {
        Write-Host "⚠️  Claude CLI配置:" -ForegroundColor Yellow
        Write-Host "  请先安装Claude CLI并运行:"
        Write-Host "  .\scripts\configure_claude_cli.ps1" -ForegroundColor Green
        Write-Host ""
    }
    
    Write-Host "🔍 故障排除:" -ForegroundColor Cyan
    Write-Host "  安装日志: " -NoNewline
    Write-Host $LogFile -ForegroundColor Green
    Write-Host "  服务日志: " -NoNewline
    Write-Host "docker logs claude-memory-global" -ForegroundColor Green
    Write-Host ""
}

function Invoke-InteractiveSetup {
    Write-Host ""
    Write-Host "🔧 交互式配置" -ForegroundColor Blue
    Write-Host ""
    
    # MCP端口配置
    $mcpPort = Read-Host "MCP服务端口 [6334]"
    if ([string]::IsNullOrEmpty($mcpPort)) { $mcpPort = "6334" }
    $script:MCPPort = $mcpPort
    
    # Qdrant端口配置
    $qdrantPort = Read-Host "Qdrant端口 [6335]"
    if ([string]::IsNullOrEmpty($qdrantPort)) { $qdrantPort = "6335" }
    $script:QdrantPort = $qdrantPort
    
    # 日志级别
    Write-Host "日志级别选择:"
    Write-Host "  1) DEBUG - 详细调试信息"
    Write-Host "  2) INFO  - 一般信息 (默认)"
    Write-Host "  3) WARNING - 仅警告和错误"
    Write-Host "  4) ERROR - 仅错误信息"
    $logChoice = Read-Host "请选择 [2]"
    
    switch ($logChoice) {
        "1" { $script:LogLevel = "DEBUG" }
        "3" { $script:LogLevel = "WARNING" }
        "4" { $script:LogLevel = "ERROR" }
        default { $script:LogLevel = "INFO" }
    }
    
    # 自动迁移确认
    $autoMigrate = Read-Host "是否自动迁移现有项目数据库? [Y/n]"
    if ([string]::IsNullOrEmpty($autoMigrate)) { $autoMigrate = "Y" }
    $script:AutoMigrate = $autoMigrate
    
    Write-Host ""
    Write-ColorOutput "配置完成:" "Green"
    Write-ColorOutput "  MCP端口: $script:MCPPort" "Green"
    Write-ColorOutput "  Qdrant端口: $script:QdrantPort" "Green"
    Write-ColorOutput "  日志级别: $script:LogLevel" "Green"
    Write-ColorOutput "  自动迁移: $script:AutoMigrate" "Green"
    Write-Host ""
}

# 主函数
function Main {
    if ($Help) {
        Show-Help
        return
    }
    
    Show-Banner
    
    Write-Host "开始安装Claude Memory MCP全局服务..." -ForegroundColor Blue
    Write-Host "安装日志将保存到: $LogFile" -ForegroundColor Blue
    Write-Host ""
    
    # 初始化变量
    $script:ClaudeCLIReady = $false
    $script:GlobalDataDir = ""
    
    # 默认配置
    $script:MCPPort = "6334"
    $script:QdrantPort = "6335"
    $script:LogLevel = "INFO"
    $script:AutoMigrate = "Y"
    
    try {
        # 检测系统环境
        Test-Dependencies
        Test-ClaudeCLI
        
        # 交互式配置(非自动模式)
        if (!$Auto) {
            Invoke-InteractiveSetup
        }
        
        # 执行安装步骤
        New-GlobalDirectories
        
        if (!$SkipBuild) {
            Build-DockerImages
        }
        
        Start-Services
        Set-ClaudeCLIConfig
        
        # 等待服务完全启动
        Start-Sleep -Seconds 5
        Test-Installation
        
        Show-Results
        
        Write-ColorOutput "🎉 Claude Memory MCP全局服务安装完成!" "Green"
    } catch {
        Write-ColorOutput "安装过程中发生错误: $($_.Exception.Message)" "Red"
        Write-ColorOutput "请查看日志: $LogFile" "Red"
        exit 1
    }
}

# 运行主函数
Main