# Claude CLI MCP 自动配置脚本 (PowerShell版本)
# Windows环境专用，支持多种连接方式和故障排除

param(
    [switch]$CheckOnly = $false,
    [switch]$TestConnection = $false,
    [string]$ServiceName = "claude-memory-global",
    [string]$OutputReport = "",
    [switch]$Verbose = $false,
    [switch]$Help = $false
)

$Version = "2.0.0"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

# 设置详细输出
if ($Verbose) {
    $VerbosePreference = "Continue"
}

function Show-Help {
    Write-Host @"
Claude CLI MCP 自动配置工具 (Windows版)

用法: .\configure_claude_cli.ps1 [参数]

参数:
  -CheckOnly        仅检查状态，不进行配置
  -TestConnection   测试MCP连接
  -ServiceName      MCP服务名称 (默认: claude-memory-global)
  -OutputReport     输出集成报告到文件
  -Verbose          详细输出
  -Help             显示此帮助信息

示例:
  .\configure_claude_cli.ps1                    # 完整配置
  .\configure_claude_cli.ps1 -CheckOnly        # 仅检查状态
  .\configure_claude_cli.ps1 -TestConnection   # 测试连接
  .\configure_claude_cli.ps1 -Verbose          # 详细模式

"@
}

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
}

function Get-ClaudeConfigDir {
    """获取Claude CLI配置目录"""
    $appDataPath = [Environment]::GetFolderPath('ApplicationData')
    return Join-Path $appDataPath "claude"
}

function Test-ClaudeCLIInstallation {
    """检查Claude CLI安装状态"""
    Write-ColorOutput "检查Claude CLI安装状态..." "Blue"
    
    $result = @{
        installed = $false
        version = $null
        path = $null
        installation_methods = @()
    }
    
    # 检查直接命令
    try {
        $claudeVersion = claude --version 2>$null
        if ($LASTEXITCODE -eq 0) {
            $result.installed = $true
            $result.version = $claudeVersion
            $result.path = (Get-Command claude -ErrorAction SilentlyContinue).Source
            Write-ColorOutput "✓ Claude CLI已安装: $($result.version)" "Green"
            return $result
        }
    } catch {
        # 继续检查其他方法
    }
    
    # 检查npx方式
    try {
        $npxVersion = npx claude --version 2>$null
        if ($LASTEXITCODE -eq 0) {
            $result.installed = $true
            $result.version = $npxVersion
            $result.path = "npx claude"
            $result.installation_methods += "npx"
            Write-ColorOutput "✓ Claude CLI通过npx可用: $($result.version)" "Green"
            return $result
        }
    } catch {
        # 继续检查
    }
    
    Write-ColorOutput "Claude CLI未安装" "Yellow"
    $result.installation_methods = @(
        "npm install -g @anthropic/claude-cli",
        "winget install Anthropic.ClaudeCLI",
        "下载Windows安装包: https://github.com/anthropics/claude-cli/releases"
    )
    
    return $result
}

function Read-ExistingConfig {
    """读取现有配置"""
    param([string]$ConfigPath)
    
    Write-ColorOutput "读取现有Claude CLI配置..." "Blue"
    
    if (Test-Path $ConfigPath) {
        try {
            $configContent = Get-Content $ConfigPath -Raw -Encoding UTF8
            $config = $configContent | ConvertFrom-Json
            Write-ColorOutput "✓ 现有配置已读取" "Green"
            return $config
        } catch {
            Write-ColorOutput "配置文件读取失败: $($_.Exception.Message)" "Yellow"
            return @{}
        }
    } else {
        Write-ColorOutput "未找到现有配置文件" "Blue"
        return @{}
    }
}

function Backup-Config {
    """备份现有配置"""
    param([string]$ConfigPath, [string]$BackupDir)
    
    if (!(Test-Path $ConfigPath)) {
        return $null
    }
    
    $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $backupFile = Join-Path $BackupDir "claude.json.backup.$timestamp"
    
    try {
        if (!(Test-Path $BackupDir)) {
            New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null
        }
        
        Copy-Item $ConfigPath $backupFile
        Write-ColorOutput "✓ 配置已备份到: $backupFile" "Green"
        return $backupFile
    } catch {
        Write-ColorOutput "配置备份失败: $($_.Exception.Message)" "Red"
        return $null
    }
}

function Test-DockerContainer {
    """检查Docker容器是否运行"""
    try {
        $containerList = docker ps --filter "name=claude-memory-global" --format "{{.Names}}" 2>$null
        return $containerList -contains "claude-memory-global"
    } catch {
        return $false
    }
}

function Test-TCPPort {
    """检查TCP端口是否开放"""
    param([int]$Port)
    
    try {
        $tcpClient = New-Object System.Net.Sockets.TcpClient
        $result = $tcpClient.BeginConnect("localhost", $Port, $null, $null)
        $success = $result.AsyncWaitHandle.WaitOne(2000, $false)
        $tcpClient.Close()
        return $success
    } catch {
        return $false
    }
}

function Test-LocalProcess {
    """检查本地进程"""
    try {
        $processes = Get-Process -Name "python*" -ErrorAction SilentlyContinue
        foreach ($proc in $processes) {
            if ($proc.CommandLine -like "*global_mcp_server*") {
                return $true
            }
        }
        return $false
    } catch {
        return $false
    }
}

function Get-MCPServiceConnection {
    """检测MCP服务连接方式"""
    Write-ColorOutput "检测MCP服务连接方式..." "Blue"
    
    $connectionInfo = @{
        method = "unknown"
        config = @{}
        available_methods = @()
    }
    
    # 检查Docker容器
    if (Test-DockerContainer) {
        $connectionInfo.available_methods += "docker_exec"
        $connectionInfo.method = "docker_exec"
        $connectionInfo.config = @{
            command = "docker"
            args = @("exec", "-i", "claude-memory-global", "python", "/app/global_mcp_server.py")
            env = @{}
        }
    }
    
    # 检查TCP端口
    if (Test-TCPPort -Port 6334) {
        $connectionInfo.available_methods += "tcp"
        if ($connectionInfo.method -eq "unknown") {
            $connectionInfo.method = "tcp"
            $connectionInfo.config = @{
                command = "nc"
                args = @("localhost", "6334")
                env = @{}
            }
        }
    }
    
    # 检查本地进程
    if (Test-LocalProcess) {
        $connectionInfo.available_methods += "stdio"
        if ($connectionInfo.method -eq "unknown") {
            $connectionInfo.method = "stdio"
            $connectionInfo.config = @{
                command = "python"
                args = @("C:\path\to\global_mcp_server.py")
                env = @{PYTHONPATH = "C:\path\to\src"}
            }
        }
    }
    
    Write-ColorOutput "✓ 检测到连接方式: $($connectionInfo.method)" "Green"
    return $connectionInfo
}

function New-MCPConfig {
    """生成MCP配置"""
    param($ConnectionInfo, [string]$ServiceName)
    
    Write-ColorOutput "生成MCP配置 (连接方式: $($ConnectionInfo.method))..." "Blue"
    
    $mcpConfig = @{
        mcpServers = @{
            $ServiceName = $ConnectionInfo.config
        }
    }
    
    # 添加服务描述
    $mcpConfig.mcpServers.$ServiceName.description = "Claude Memory 全局记忆管理服务 - 跨项目智能记忆共享"
    
    # 根据连接方式添加特定配置
    switch ($ConnectionInfo.method) {
        "docker_exec" {
            $mcpConfig.mcpServers.$ServiceName.restart_policy = "on_failure"
            $mcpConfig.mcpServers.$ServiceName.timeout = 30
        }
        "tcp" {
            $mcpConfig.mcpServers.$ServiceName.connection_timeout = 10
            $mcpConfig.mcpServers.$ServiceName.retry_attempts = 3
        }
    }
    
    return $mcpConfig
}

function Merge-Configurations {
    """合并配置"""
    param($ExistingConfig, $NewMCPConfig)
    
    Write-ColorOutput "合并Claude CLI配置..." "Blue"
    
    # 转换为哈希表进行操作
    $mergedConfig = @{}
    
    # 复制现有配置
    if ($ExistingConfig) {
        $ExistingConfig.PSObject.Properties | ForEach-Object {
            $mergedConfig[$_.Name] = $_.Value
        }
    }
    
    # 确保mcpServers字段存在
    if (!$mergedConfig.ContainsKey('mcpServers')) {
        $mergedConfig['mcpServers'] = @{}
    }
    
    # 合并MCP服务器配置
    $NewMCPConfig.mcpServers.PSObject.Properties | ForEach-Object {
        $mergedConfig['mcpServers'][$_.Name] = $_.Value
    }
    
    # 添加元数据
    if (!$mergedConfig.ContainsKey('metadata')) {
        $mergedConfig['metadata'] = @{}
    }
    
    $mergedConfig['metadata']['claude_memory_integration'] = @{
        version = "2.0.0"
        last_updated = (Get-Date).ToString("yyyy-MM-ddTHH:mm:ss")
        auto_configured = $true
    }
    
    Write-ColorOutput "✓ 配置合并完成" "Green"
    return $mergedConfig
}

function Write-Config {
    """写入配置文件"""
    param($Config, [string]$ConfigPath)
    
    Write-ColorOutput "写入Claude CLI配置文件..." "Blue"
    
    try {
        # 确保目录存在
        $configDir = Split-Path $ConfigPath -Parent
        if (!(Test-Path $configDir)) {
            New-Item -ItemType Directory -Path $configDir -Force | Out-Null
        }
        
        # 转换为JSON并写入
        $jsonConfig = $Config | ConvertTo-Json -Depth 10
        $jsonConfig | Out-File -FilePath $ConfigPath -Encoding UTF8
        
        # 验证文件
        try {
            Get-Content $ConfigPath -Raw | ConvertFrom-Json | Out-Null
            Write-ColorOutput "✓ 配置文件格式验证通过" "Green"
        } catch {
            Write-ColorOutput "配置文件格式无效: $($_.Exception.Message)" "Red"
            return $false
        }
        
        Write-ColorOutput "✓ 配置文件已写入: $ConfigPath" "Green"
        return $true
        
    } catch {
        Write-ColorOutput "配置文件写入失败: $($_.Exception.Message)" "Red"
        return $false
    }
}

function Test-MCPConnection {
    """测试MCP连接"""
    param([string]$ServiceName)
    
    Write-ColorOutput "测试MCP服务器连接..." "Blue"
    
    $testResult = @{
        success = $false
        service_found = $false
        ping_success = $false
        tools_available = $false
        error = $null
    }
    
    try {
        # 测试列出MCP服务器
        $listOutput = claude mcp list 2>&1
        if ($LASTEXITCODE -eq 0) {
            if ($listOutput -like "*$ServiceName*") {
                $testResult.service_found = $true
                Write-ColorOutput "✓ $ServiceName 服务器已注册" "Green"
                
                # 测试ping
                $pingOutput = claude mcp call $ServiceName ping 2>&1
                if ($LASTEXITCODE -eq 0) {
                    $testResult.ping_success = $true
                    Write-ColorOutput "✓ MCP服务器ping测试成功" "Green"
                    
                    # 测试工具列表
                    $toolsOutput = claude mcp tools $ServiceName 2>&1
                    if ($LASTEXITCODE -eq 0) {
                        $testResult.tools_available = $true
                        Write-ColorOutput "✓ MCP工具列表获取成功" "Green"
                        $testResult.success = $true
                    } else {
                        $testResult.error = "工具列表获取失败: $toolsOutput"
                    }
                } else {
                    $testResult.error = "Ping测试失败: $pingOutput"
                }
            } else {
                $testResult.error = "$ServiceName 未在MCP服务器列表中找到"
            }
        } else {
            $testResult.error = "无法获取MCP服务器列表: $listOutput"
        }
    } catch {
        $testResult.error = "测试过程中发生错误: $($_.Exception.Message)"
    }
    
    if ($testResult.success) {
        Write-ColorOutput "✓ MCP连接测试通过" "Green"
    } else {
        Write-ColorOutput "⚠ MCP连接测试失败: $($testResult.error)" "Yellow"
    }
    
    return $testResult
}

function Invoke-AutoIntegration {
    """执行自动集成"""
    param([string]$ServiceName)
    
    Write-ColorOutput "开始Claude CLI自动集成设置..." "Blue"
    
    $integrationResult = @{
        success = $false
        steps_completed = @()
        warnings = @()
        errors = @()
    }
    
    try {
        # 1. 检查Claude CLI
        $cliStatus = Test-ClaudeCLIInstallation
        if (!$cliStatus.installed) {
            $integrationResult.errors += "Claude CLI未安装"
            return $integrationResult
        }
        $integrationResult.steps_completed += "Claude CLI检查通过"
        
        # 2. 设置路径
        $configDir = Get-ClaudeConfigDir
        $configFile = Join-Path $configDir "claude.json"
        $backupDir = Join-Path $configDir "backups"
        
        # 3. 备份现有配置
        $backupPath = Backup-Config -ConfigPath $configFile -BackupDir $backupDir
        if ($backupPath) {
            $integrationResult.steps_completed += "配置已备份: $backupPath"
        }
        
        # 4. 读取现有配置
        $existingConfig = Read-ExistingConfig -ConfigPath $configFile
        $integrationResult.steps_completed += "现有配置已读取"
        
        # 5. 检测MCP服务连接方式
        $connectionInfo = Get-MCPServiceConnection
        if ($connectionInfo.method -eq "unknown") {
            $integrationResult.warnings += "未检测到活跃的MCP服务"
        }
        $integrationResult.steps_completed += "连接方式检测: $($connectionInfo.method)"
        
        # 6. 生成MCP配置
        $mcpConfig = New-MCPConfig -ConnectionInfo $connectionInfo -ServiceName $ServiceName
        $integrationResult.steps_completed += "MCP配置已生成"
        
        # 7. 合并配置
        $finalConfig = Merge-Configurations -ExistingConfig $existingConfig -NewMCPConfig $mcpConfig
        $integrationResult.steps_completed += "配置已合并"
        
        # 8. 写入配置文件
        if (Write-Config -Config $finalConfig -ConfigPath $configFile) {
            $integrationResult.steps_completed += "配置文件已写入"
        } else {
            $integrationResult.errors += "配置文件写入失败"
            return $integrationResult
        }
        
        # 9. 测试连接
        $testResult = Test-MCPConnection -ServiceName $ServiceName
        if ($testResult.success) {
            $integrationResult.steps_completed += "MCP连接测试通过"
            $integrationResult.success = $true
        } else {
            $integrationResult.warnings += "MCP连接测试失败: $($testResult.error)"
            $integrationResult.success = $true  # 配置成功，但连接测试失败
        }
        
    } catch {
        $integrationResult.errors += "集成过程中发生错误: $($_.Exception.Message)"
        Write-ColorOutput "自动集成失败: $($_.Exception.Message)" "Red"
    }
    
    return $integrationResult
}

function New-IntegrationReport {
    """生成集成报告"""
    param($IntegrationResult)
    
    $reportLines = @(
        "Claude CLI MCP 集成报告 (Windows版)",
        "=" * 50,
        "集成时间: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')",
        "操作系统: Windows",
        "配置目录: $(Get-ClaudeConfigDir)",
        "",
        "集成结果: $(if ($IntegrationResult.success) { '成功' } else { '失败' })",
        ""
    )
    
    if ($IntegrationResult.steps_completed.Count -gt 0) {
        $reportLines += "完成的步骤:"
        $IntegrationResult.steps_completed | ForEach-Object {
            $reportLines += "  ✓ $_"
        }
        $reportLines += ""
    }
    
    if ($IntegrationResult.warnings.Count -gt 0) {
        $reportLines += "警告:"
        $IntegrationResult.warnings | ForEach-Object {
            $reportLines += "  ⚠ $_"
        }
        $reportLines += ""
    }
    
    if ($IntegrationResult.errors.Count -gt 0) {
        $reportLines += "错误:"
        $IntegrationResult.errors | ForEach-Object {
            $reportLines += "  ✗ $_"
        }
        $reportLines += ""
    }
    
    # 添加使用说明
    if ($IntegrationResult.success) {
        $reportLines += @(
            "使用说明:",
            "  1. 列出MCP服务器: claude mcp list",
            "  2. 搜索记忆: claude mcp call claude-memory-global memory_search '{\"query\": \"your search\"}'",
            "  3. 获取最近对话: claude mcp call claude-memory-global get_recent_conversations",
            "  4. 健康检查: claude mcp call claude-memory-global ping",
            ""
        )
    }
    
    return $reportLines -join "`n"
}

function Show-ConfigurationResult {
    """显示配置结果"""
    param($IntegrationResult)
    
    Write-Host ""
    Write-Host "╔═══════════════════════════════════════════════════════════════╗" -ForegroundColor Green
    Write-Host "║                                                               ║" -ForegroundColor Green
    Write-Host "║              🔧 Windows Claude CLI配置完成! 🔧                ║" -ForegroundColor Green
    Write-Host "║                                                               ║" -ForegroundColor Green
    Write-Host "╚═══════════════════════════════════════════════════════════════╝" -ForegroundColor Green
    Write-Host ""
    
    $configDir = Get-ClaudeConfigDir
    Write-Host "📋 配置信息:" -ForegroundColor Cyan
    Write-Host "  配置文件: " -NoNewline
    Write-Host "$configDir\claude.json" -ForegroundColor Green
    Write-Host "  MCP服务器: " -NoNewline
    Write-Host "claude-memory-global" -ForegroundColor Green
    Write-Host ""
    
    Write-Host "🚀 使用方法:" -ForegroundColor Cyan
    Write-Host "  1. 打开PowerShell或命令提示符"
    Write-Host "  2. 列出MCP服务器: " -NoNewline
    Write-Host "claude mcp list" -ForegroundColor Green
    Write-Host "  3. 调用记忆搜索: " -NoNewline
    Write-Host "claude mcp call claude-memory-global memory_search" -ForegroundColor Green
    Write-Host "  4. 获取最近对话: " -NoNewline
    Write-Host "claude mcp call claude-memory-global get_recent_conversations" -ForegroundColor Green
    Write-Host ""
    
    Write-Host "🛠️  可用MCP工具:" -ForegroundColor Cyan
    Write-Host "  • " -NoNewline
    Write-Host "memory_search" -ForegroundColor Green -NoNewline
    Write-Host " - 搜索全局对话记忆"
    Write-Host "  • " -NoNewline
    Write-Host "get_recent_conversations" -ForegroundColor Green -NoNewline
    Write-Host " - 获取最近对话"
    Write-Host "  • " -NoNewline
    Write-Host "memory_status" -ForegroundColor Green -NoNewline
    Write-Host " - 系统状态信息"
    Write-Host "  • " -NoNewline
    Write-Host "ping" -ForegroundColor Green -NoNewline
    Write-Host " - 连接测试"
    Write-Host ""
    
    Write-Host "🔍 Windows故障排除:" -ForegroundColor Cyan
    Write-Host "  查看配置: " -NoNewline
    Write-Host "Get-Content $configDir\claude.json" -ForegroundColor Green
    Write-Host "  列出服务器: " -NoNewline
    Write-Host "claude mcp list" -ForegroundColor Green
    Write-Host "  测试连接: " -NoNewline
    Write-Host "claude mcp call claude-memory-global ping" -ForegroundColor Green
    Write-Host "  查看服务日志: " -NoNewline
    Write-Host "docker logs claude-memory-global" -ForegroundColor Green
    Write-Host ""
}

# 主函数
function Main {
    if ($Help) {
        Show-Help
        return
    }
    
    Write-Host "Claude CLI MCP 自动配置工具 (Windows版) v$Version" -ForegroundColor Blue
    Write-Host ""
    
    try {
        if ($CheckOnly) {
            # 仅检查状态
            $cliStatus = Test-ClaudeCLIInstallation
            $connectionInfo = Get-MCPServiceConnection
            
            Write-Host "Claude CLI状态检查:" -ForegroundColor Cyan
            Write-Host "  安装状态: $(if ($cliStatus.installed) { '已安装' } else { '未安装' })"
            if ($cliStatus.installed) {
                Write-Host "  版本: $($cliStatus.version)"
                Write-Host "  路径: $($cliStatus.path)"
            }
            
            Write-Host "`nMCP服务连接检测:" -ForegroundColor Cyan
            Write-Host "  推荐连接方式: $($connectionInfo.method)"
            Write-Host "  可用连接方式: $($connectionInfo.available_methods -join ', ')"
            
        } elseif ($TestConnection) {
            # 测试连接
            $testResult = Test-MCPConnection -ServiceName $ServiceName
            Write-Host "MCP连接测试结果:" -ForegroundColor Cyan
            Write-Host "  整体成功: $($testResult.success)"
            Write-Host "  服务发现: $($testResult.service_found)"
            Write-Host "  Ping测试: $($testResult.ping_success)"
            Write-Host "  工具可用: $($testResult.tools_available)"
            if ($testResult.error) {
                Write-Host "  错误信息: $($testResult.error)"
            }
        } else {
            # 执行完整集成
            Write-Host "开始Claude CLI MCP自动集成..." -ForegroundColor Blue
            $integrationResult = Invoke-AutoIntegration -ServiceName $ServiceName
            
            # 生成报告
            $report = New-IntegrationReport -IntegrationResult $integrationResult
            Write-Host $report
            
            # 显示结果
            if ($integrationResult.success) {
                Show-ConfigurationResult -IntegrationResult $integrationResult
            }
            
            # 保存报告
            if ($OutputReport) {
                $report | Out-File -FilePath $OutputReport -Encoding UTF8
                Write-Host "`n报告已保存到: $OutputReport" -ForegroundColor Green
            }
            
            # 退出码
            if (!$integrationResult.success) {
                exit 1
            }
        }
    } catch {
        Write-ColorOutput "配置过程中发生错误: $($_.Exception.Message)" "Red"
        exit 1
    }
}

# 运行主函数
Main