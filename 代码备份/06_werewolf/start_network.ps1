# 启动狼人杀游戏网络
# Start Werewolf Game Network

Write-Host "🐺 Starting Werewolf Game Network..." -ForegroundColor Cyan

# 切换到 demo 目录
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir

# 检查 .env 文件
if (-not (Test-Path ".env")) {
    Write-Host "⚠️ Warning: .env file not found. LLM may not work properly." -ForegroundColor Yellow
}

# 启动网络 (From Source)
Write-Host "📡 Starting network on port 8700 (Source Mode)..." -ForegroundColor Green
$env:PYTHONPATH = "$scriptDir\..\..\src;" + $env:PYTHONPATH
python -m openagents.cli network run network.yaml

