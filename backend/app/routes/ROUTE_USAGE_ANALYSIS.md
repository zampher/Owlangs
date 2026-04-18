# Routes/Service 使用情况分析

## 检查结果总结

### ✅ 路径匹配情况

前端调用的路径与 `routes/service/` 中定义的路由路径**完全匹配**：

| 前端调用路径 | HTTP 方法 | routes/service 路由 | 状态 |
|------------|----------|-------------------|------|
| `/service/translate` | POST | `translation.py` → `/translate` | ✅ 匹配 |
| `/service/status/{taskId}` | GET | `status.py` → `/status/{task_id}` | ✅ 匹配 |
| `/service/logs/{taskId}` | GET | `status.py` → `/logs/{task_id}` | ✅ 匹配 |
| `/service/cancel/{taskId}` | POST | `translation.py` → `/cancel/{task_id}` | ✅ 匹配 |
| `/service/release/{taskId}` | POST | `translation.py` → `/release/{task_id}` | ✅ 匹配 |
| `/service/download/{taskId}/{fileType}` | GET | `download.py` → `/download/{task_id}/{file_type}` | ✅ 匹配 |
| `/service/source-preview/{taskId}` | GET | `status.py` → `/source-preview/{task_id}` | ✅ 匹配 |
| `/service/layout-extract/{taskId}` | GET | `status.py` → `/layout-extract/{task_id}` | ✅ 匹配 |
| `/service/source-resplit/{taskId}` | POST | `format_conversion.py` → `/source-resplit/{task_id}` | ✅ 匹配 |
| `/service/convert-format` | POST | `format_conversion.py` → `/convert-format` | ✅ 匹配 |

### ⚠️ 需要注意的路径

| 前端调用路径 | HTTP 方法 | routes/service 路由 | 状态 |
|------------|----------|-------------------|------|
| `/service/debug/{taskId}` | GET | `download.py` → `/debug/{task_id}/{file_type}` | ⚠️ 路径不匹配 |
| `/service/engin-list` | GET | `misc.py` → `/engin-list` | ❓ 未找到前端调用 |
| `/service/task-list` | GET | `misc.py` → `/task-list` | ❓ 未找到前端调用 |
| `/service/default-params` | GET | `misc.py` → `/default-params` | ❓ 未找到前端调用 |
| `/service/meta` | GET | `misc.py` → `/meta` | ❓ 未找到前端调用 |

### 🔍 详细分析

#### 1. Debug 路径不匹配问题

**前端调用**：
```dart
// frontend/lib/shared/services/translation_service.dart:94
return '/service/debug/$taskId/$fileType';
```

**后端定义**：
```python
# backend/app/routes/service/download.py:67
@router.get("/debug/{task_id}/{file_type}", ...)
```

**结论**：✅ 实际上路径是匹配的！前端代码中 `buildDebugUrl` 方法返回的是 `/service/debug/$taskId/$fileType`，与后端定义一致。

#### 2. Misc 路由使用情况

**检查结果**：
- `misc.py` 中定义了 4 个路由：
  - `/engin-list` - GET
  - `/task-list` - GET
  - `/default-params` - GET
  - `/meta` - GET

- **前端代码中未找到对这些路由的直接调用**
- 这些路由可能：
  1. 被其他前端（如 Vue 前端）使用
  2. 被后端内部调用
  3. 暂时未使用（预留接口）

#### 3. 路由注册情况

**当前状态**：
- `routes/service/` 中的路由**没有被注册**到 FastAPI 应用中
- `factory.py` 中只注册了 `service_router`（来自 `app_routes_service.py`）
- 前端实际访问的是 `app_routes_service.py` 中的旧路由

**路径对比**：
- `app_routes_service.py` 中的路由路径与 `routes/service/` 中的路径**完全一致**
- 这意味着如果注册 `routes/service/` 中的路由，前端**无需修改**即可使用

## 结论

### ✅ 路径兼容性：100% 兼容

**`routes/service/` 中定义的路由路径与前端调用的路径完全匹配**，这意味着：

1. **可以直接替换**：注册 `routes/service/` 中的路由后，前端无需修改即可使用
2. **路径一致**：所有前端调用的路径都能在 `routes/service/` 中找到对应的路由定义
3. **向后兼容**：替换后不会影响前端功能

### ⚠️ 当前问题

1. **路由未注册**：`routes/service/` 中的路由没有被注册到 FastAPI 应用中
2. **前端使用旧路由**：前端实际访问的是 `app_routes_service.py` 中的旧路由
3. **代码重复**：存在两套路由定义，但只有一套在使用

### 📋 建议

1. **立即注册新路由**：在 `factory.py` 中注册 `routes/service/` 中的路由
2. **测试验证**：确保所有路由正常工作
3. **逐步迁移**：重构路由调用逻辑，让它们调用服务层
4. **清理旧代码**：确认新路由完全正常后，可以移除 `app_routes_service.py` 中的旧路由

## 前端调用路径清单

### Translation Service (`translation_service.dart`)
- ✅ `/service/translate` - POST
- ✅ `/service/status/{taskId}` - GET
- ✅ `/service/logs/{taskId}` - GET
- ✅ `/service/cancel/{taskId}` - POST
- ✅ `/service/release/{taskId}` - POST
- ✅ `/service/download/{taskId}/{fileType}` - GET (buildDownloadUrl)
- ✅ `/service/debug/{taskId}/{fileType}` - GET (buildDebugUrl)
- ✅ `/service/source-preview/{taskId}` - GET
- ✅ `/service/layout-extract/{taskId}` - GET
- ✅ `/service/source-resplit/{taskId}` - POST

### Format Conversion Service (`format_conversion_service.dart`)
- ✅ `/service/convert-format` - POST

### 其他可能的调用
- ❓ `/service/engin-list` - GET (未找到前端调用)
- ❓ `/service/task-list` - GET (未找到前端调用)
- ❓ `/service/default-params` - GET (未找到前端调用)
- ❓ `/service/meta` - GET (未找到前端调用)

## 下一步行动

1. ✅ **确认路径兼容性** - 已完成，100% 兼容
2. ⏳ **注册新路由** - 在 `factory.py` 中注册 `routes/service/` 中的路由
3. ⏳ **测试验证** - 确保所有路由正常工作
4. ⏳ **重构路由逻辑** - 让路由调用服务层而不是 `app_routes_service.py` 中的函数

