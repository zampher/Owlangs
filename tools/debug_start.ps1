# Owlangs 快速调试启动脚本 (PowerShell)
# 用于开发环境快速启动应用，支持Redis启用/禁用选择

# 解析命令行参数
param(
    [switch]$EnableRedis,
    [switch]$DisableRedis
)

Write-Host "🚀 Owlangs 调试模式启动脚本" -ForegroundColor Green
Write-Host "==================================" -ForegroundColor Green

# 设置Redis环境变量
if ($EnableRedis) {
    $env:REDIS_ENABLED = "true"
    Write-Host "✅ 已启用Redis (REDIS_ENABLED=true)" -ForegroundColor Green
} elseif ($DisableRedis) {
    $env:REDIS_ENABLED = "false"
    Write-Host "✅ 已禁用Redis (REDIS_ENABLED=false)" -ForegroundColor Yellow
} else {
    $env:REDIS_ENABLED = "false"
    Write-Host "✅ 默认禁用Redis (REDIS_ENABLED=false)" -ForegroundColor Yellow
}

# 检查是否在正确的目录
if (-not (Test-Path "pyproject.toml")) {
    Write-Host "❌ 错误: 请在Owlangs项目根目录下运行此脚本" -ForegroundColor Red
    Write-Host "   当前目录: $PWD" -ForegroundColor Red
    Write-Host "   请切换到项目根目录: cd D:\path\to\Owlangs" -ForegroundColor Red
    Read-Host "按任意键退出"
    exit 1
}

# 检查uv是否安装
try {
    $uvVersion = uv --version 2>$null
    if ($LASTEXITCODE -ne 0) {
        throw "uv not found"
    }
} catch {
    Write-Host "❌ 错误: 未找到uv命令" -ForegroundColor Red
    Write-Host "   请先安装uv: https://docs.astral.sh/uv/getting-started/installation/" -ForegroundColor Red
    Read-Host "按任意键退出"
    exit 1
}

Write-Host "📦 使用uv启动Owlangs..." -ForegroundColor Cyan
Write-Host "   命令: uv run python -m backend.cli -i" -ForegroundColor Gray
Write-Host "   环境: REDIS_ENABLED=$env:REDIS_ENABLED" -ForegroundColor Gray
Write-Host ""

# 启动应用
uv run python -m backend.cli -i

# 保持窗口打开
Read-Host "按任意键退出"
