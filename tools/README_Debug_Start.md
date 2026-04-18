# Owlangs 调试启动脚本

这些脚本用于快速启动Owlangs应用进行调试，支持灵活的Redis配置选项。

## 📁 脚本文件

### Linux/macOS
- **`debug_start.sh`** - Bash脚本，适用于Linux和macOS

### Windows
- **`debug_start.bat`** - 批处理文件，适用于Windows命令行
- **`debug_start.ps1`** - PowerShell脚本，适用于Windows PowerShell

## 🚀 使用方法

### Linux/macOS
```bash
# 给脚本添加执行权限
chmod +x tools/debug_start.sh

# 默认禁用Redis
./tools/debug_start.sh

# 启用Redis
./tools/debug_start.sh --enable-redis

# 禁用Redis (显式)
./tools/debug_start.sh --disable-redis
```

### Windows (命令行)
```cmd
# 默认禁用Redis
tools\debug_start.bat

# 启用Redis
tools\debug_start.bat --enable-redis

# 禁用Redis (显式)
tools\debug_start.bat --disable-redis
```

### Windows (PowerShell)
```powershell
# 默认禁用Redis
.\tools\debug_start.ps1

# 启用Redis
.\tools\debug_start.ps1 -EnableRedis

# 禁用Redis (显式)
.\tools\debug_start.ps1 -DisableRedis
```

## ⚙️ 脚本功能

1. **灵活Redis控制**: 支持通过命令行参数选择启用或禁用Redis
2. **默认行为**: 脚本默认禁用Redis，便于调试
3. **配置支持**: 直接使用 `uv run python -m backend.cli -i` 时，Redis行为由配置文件控制（默认启用）
4. **检查项目目录**: 确保在Owlangs项目根目录
5. **检查uv安装**: 确保已安装uv包管理器
6. **启动应用**: 使用 `uv run python -m backend.cli -i`

## 🔧 环境要求

- **uv**: 必须安装uv包管理器
- **Python**: 项目依赖的Python版本
- **项目目录**: 必须在Owlangs项目根目录下运行

## 📝 注意事项

- **调试脚本**: 默认禁用Redis，适用于调试环境
- **生产环境**: 直接使用 `uv run python -m backend.cli -i`，Redis行为由配置文件控制（默认启用）
- **会话管理**: 如果Redis被禁用，会话管理功能将不可用
- **参数优先级**: 环境变量 > 配置文件 > 默认值

## 🐛 故障排除

### 错误: 未找到uv命令
```bash
# 安装uv
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 错误: 请在Owlangs项目根目录下运行
```bash
# 切换到项目根目录
cd /path/to/Owlangs
```

### Windows PowerShell执行策略问题
```powershell
# 设置执行策略
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```
