# 配置管理系统

## 概述

Owlangs 使用分层配置架构，将系统级配置和用户级配置分离，便于管理和维护。

## 配置架构

### 1. 全局配置 (GlobalConfig)
- **文件位置**: `*global_config.json`
- **用途**: 存储系统级配置和敏感信息
- **权限**: 只有管理员可以修改
- **内容**:
  - API密钥和模型配置
  - 解析引擎设置
  - 系统级参数

### 2. 用户配置模板 (Templates)
- **目录位置**: `docutranslate/config/templates/`
- **用途**: 存储配置模板，用于初始化新用户
- **模板类型**:
  - `default_profile.json` - 统一配置模板（管理员和普通用户共用）

### 3. 用户实际配置 (User Profiles)
- **目录位置**: `user_profiles/`
- **用途**: 存储每个用户的个性化配置
- **文件格式**: `{username}_profile.json`
- **权限**: 每个用户只能修改自己的配置

## 配置管理工具

使用 `profile_manager.py` 工具管理用户配置：

### 基本命令

```bash
# 列出所有模板和用户配置
python3 profile_manager.py list

# 从模板创建用户配置（使用统一模板）
python3 profile_manager.py create --username <username>

# 删除用户配置
python3 profile_manager.py delete --username <username>

# 备份用户配置
python3 profile_manager.py backup --username <username>

# 从备份恢复用户配置
python3 profile_manager.py restore --username <username>

# 获取用户配置信息
python3 profile_manager.py info --username <username>

# 验证用户配置完整性
python3 profile_manager.py validate --username <username>
```

### 使用示例

```bash
# 创建新用户配置（使用统一模板）
python3 profile_manager.py create --username john

# 创建管理员配置（使用统一模板）
python3 profile_manager.py create --username admin

# 备份所有用户配置
for user in $(python3 profile_manager.py list | grep "用户配置:" | cut -d'[' -f2 | cut -d']' -f1 | tr -d "'" | tr ',' ' '); do
    python3 profile_manager.py backup --username $user
done
```

## 配置字段说明

### 统一配置模板 (default_profile.json)
- 包含所有配置选项
- 默认语言: 中文
- 默认目标语言: 英文
- 管理员和普通用户使用相同模板
- 权限控制通过UI层面实现，而非配置层面

## 配置更新流程

1. **修改模板**: 更新 `templates/default_profile.json` 文件
2. **创建新用户**: 系统自动从统一模板创建配置
3. **更新现有用户**: 手动备份后从新模板重新创建
4. **管理员设置生效**: 管理员修改配置后，新用户自动获得最新配置

## 安全考虑

- 敏感信息（API密钥等）只存储在全局配置中
- 用户配置不包含敏感信息
- 管理员和普通用户使用相同的配置模板，权限通过UI控制
- 支持配置备份和恢复

## 故障排除

### 配置文件损坏
```bash
# 验证配置完整性
python3 profile_manager.py validate --username <username>

# 从备份恢复
python3 profile_manager.py restore --username <username>
```

### 模板文件缺失
```bash
# 检查模板文件
ls -la templates/

# 重新创建模板文件
# 参考现有的 admin_profile.json 和 user_profile.json
```

### 权限问题
```bash
# 检查目录权限
ls -la user_profiles/
ls -la templates/

# 修复权限
chmod 755 user_profiles/
chmod 644 user_profiles/*.json
```
