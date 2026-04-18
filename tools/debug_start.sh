#!/bin/bash
# Owlangs 快速调试启动脚本
# 用于开发环境快速启动应用，支持Redis启用/禁用选择

# 解析命令行参数
REDIS_ENABLED=false
if [ "$1" = "--enable-redis" ]; then
    REDIS_ENABLED=true
    echo "✅ 已启用Redis (REDIS_ENABLED=true)"
elif [ "$1" = "--disable-redis" ]; then
    REDIS_ENABLED=false
    echo "✅ 已禁用Redis (REDIS_ENABLED=false)"
elif [ -z "$1" ]; then
    REDIS_ENABLED=false
    echo "✅ 默认禁用Redis (REDIS_ENABLED=false)"
else
    echo "❌ 未知参数: $1"
    echo "用法: $0 [--enable-redis|--disable-redis]"
    echo "  --enable-redis   : 启用Redis"
    echo "  --disable-redis  : 禁用Redis (默认)"
    echo "  无参数           : 禁用Redis"
    exit 1
fi

echo "🚀 Owlangs 调试模式启动脚本"
echo "=================================="

# 设置Redis环境变量
export REDIS_ENABLED=$REDIS_ENABLED

# 检查是否在正确的目录
if [ ! -f "pyproject.toml" ]; then
    echo "❌ 错误: 请在Owlangs项目根目录下运行此脚本"
    echo "   当前目录: $(pwd)"
    echo "   请切换到项目根目录: cd /path/to/Owlangs"
    exit 1
fi

# 检查uv是否安装
if ! command -v uv &> /dev/null; then
    echo "❌ 错误: 未找到uv命令"
    echo "   请先安装uv: curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

echo "📦 使用uv启动Owlangs..."
echo "   命令: uv run python -m backend.cli -i"
echo "   环境: REDIS_ENABLED=$REDIS_ENABLED"
echo ""

# 启动应用
uv run python -m backend.cli -i
