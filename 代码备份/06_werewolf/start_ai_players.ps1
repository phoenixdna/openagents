# 启动 AI 玩家 (6个)
# Start AI Players for Werewolf Game

Write-Host "🤖 Starting AI Players..." -ForegroundColor Cyan

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir

# 等待网络启动
Write-Host "⏳ Waiting for network to be ready..." -ForegroundColor Yellow
Start-Sleep -Seconds 3

# 启动所有 AI 玩家
$players = @(
    "agents/ai_player1.yaml",
    "agents/ai_player2.yaml",
    "agents/ai_player3.yaml",
    "agents/ai_player4.yaml",
    "agents/ai_player5.yaml"
    # "agents/ai_player6.yaml" # Disabled: Game requires 1 Human + 5 AI
)

foreach ($player in $players) {
    $name = [System.IO.Path]::GetFileNameWithoutExtension($player)
    Write-Host "🚀 Starting $name..." -ForegroundColor Green
    $env:PYTHONPATH = "$scriptDir\..\..\src;" + $env:PYTHONPATH
    Start-Process -NoNewWindow -FilePath "python" -ArgumentList "-m", "openagents.cli", "agent", "run", $player
    Start-Sleep -Seconds 1
}

Write-Host ""
Write-Host "✅ All AI players started!" -ForegroundColor Green
Write-Host "📺 Open http://localhost:8700/studio to view the game" -ForegroundColor Cyan
Write-Host ""
Write-Host "Game will auto-start when all 6 players join." -ForegroundColor White

# 保持脚本运行
Write-Host "Press Ctrl+C to stop all players..."
while ($true) { Start-Sleep -Seconds 10 }

