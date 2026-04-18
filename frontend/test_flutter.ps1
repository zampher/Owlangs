# Flutter测试脚本
Write-Host "🚀 测试Flutter前端项目..." -ForegroundColor Green

# 检查Flutter版本
Write-Host "📋 检查Flutter版本..." -ForegroundColor Yellow
E:\software\Dev\Flutter\flutter\bin\flutter --version

# 检查项目依赖
Write-Host "📦 安装项目依赖..." -ForegroundColor Yellow
E:\software\Dev\Flutter\flutter\bin\flutter pub get

# 检查可用设备
Write-Host "📱 检查可用设备..." -ForegroundColor Yellow
E:\software\Dev\Flutter\flutter\bin\flutter devices

# 分析项目
Write-Host "🔍 分析项目代码..." -ForegroundColor Yellow
E:\software\Dev\Flutter\flutter\bin\flutter analyze

Write-Host "✅ Flutter项目测试完成!" -ForegroundColor Green


