# 滚动性能分析报告

## 1. addPostFrameCallback 使用情况

### 1.1 滚动相关（影响性能）
- **`synchronized_scroll_mixin.dart`** (第234行、第333行)
  - **频率**: 每次滚动事件都会调用
  - **用途**: 在下一帧执行同步滚动操作
  - **问题**: 当主线程被阻塞时，延迟会累积（日志显示延迟可达 590ms+）
  - **影响**: ⚠️ **高影响** - 这是滚动同步的核心机制

### 1.2 非滚动相关（不影响滚动性能）
- **`translation_screen.dart`** (第67、72、165、438行)
  - **频率**: 仅在初始化或状态变化时调用
  - **用途**: 初始化版本栈、加载持久化状态、保存步骤状态
  - **影响**: ✅ **低影响** - 不在滚动时执行

- **`translation_result_preview.dart`** (第385、1228、1278、1345行)
  - **频率**: 仅在用户操作（编辑、跳转段落）时调用
  - **用途**: 滚动到特定段落、刷新内容
  - **影响**: ✅ **低影响** - 不在滚动时执行

## 2. Widget 重建分析

### 2.1 左侧原始文本区域
**位置**: `extract_preview.dart` 第649行
```dart
SelectableText(_original)
```

**问题**:
- 每次滚动时，`SingleChildScrollView` 可能触发 `SelectableText` 重建
- `SelectableText` 对于长文本（可能数千字符）的布局计算较慢
- 日志显示有慢构建检测（>5ms）

**影响**: ⚠️ **中等影响** - 取决于文本长度

**优化建议**:
- 使用 `RepaintBoundary` 包裹 `SelectableText`
- 考虑使用 `Text` 替代 `SelectableText`（如果不需要选择功能）
- 使用 `AutomaticKeepAliveClientMixin` 保持状态

### 2.2 右侧分段列表区域
**位置**: `extract_preview.dart` 第728-750行
```dart
ListView.separated(
  itemBuilder: (context, i) {
    SegmentNumberedItem(...)
  }
)
```

**问题**:
- 滚动时会重建可见的 `SegmentNumberedItem`
- 每个 `SegmentNumberedItem` 包含：
  - `SelectableText` (第92行) - 文本布局计算
  - `MouseRegion` (第53行) - hover 状态管理
  - `GestureDetector` (第56行) - 点击检测
  - 装饰和样式计算
- 日志显示有慢构建检测（>10ms）

**影响**: ⚠️ **高影响** - 滚动时频繁重建

**优化建议**:
- 使用 `ListView.builder` 的 `cacheExtent` 参数限制缓存范围
- 为 `SegmentNumberedItem` 添加 `const` 构造函数（如果可能）
- 使用 `RepaintBoundary` 包裹每个 item
- 考虑使用 `SliverList` 替代 `ListView.separated`

### 2.3 SegmentNumberedItem 内部
**位置**: `segment_numbered_item.dart`

**组件结构**:
1. `MouseRegion` - hover 状态（每次 hover 触发 `setState`）
2. `GestureDetector` - 点击检测
3. `Container` - 装饰和边框
4. `SelectableText` - 文本显示（可能很慢）

**问题**:
- `MouseRegion` 的 `onEnter`/`onExit` 会触发 `setState`，导致整个 item 重建
- `SelectableText` 的布局计算可能较慢

**影响**: ⚠️ **中等影响** - hover 时会重建

## 3. 复杂计算分析

### 3.1 GlobalKey 重建
**位置**: `extract_preview.dart` 第104-114行
```dart
void _updateSegmentKeys() {
  _segmentKeys.clear();
  for (int i = 0; i < items.length; i++) {
    _segmentKeys[i] = GlobalKey();
  }
}
```

**问题**:
- 在分页变化时重建所有 GlobalKey
- 虽然不在滚动时执行，但可能影响整体性能

**影响**: ✅ **低影响** - 仅在分页时执行

### 3.2 同步滚动计算
**位置**: `synchronized_scroll_mixin.dart` 第368-431行
```dart
void _syncScroll(ScrollController source, ScrollController? target) {
  // 计算比例、目标位置等
  final ratio = sourceOffset / sourceMaxScroll;
  final targetOffset = ratio * targetMaxScroll;
  // ...
}
```

**问题**:
- 计算本身很快（日志显示 0-3ms）
- 但通过 `addPostFrameCallback` 异步执行，延迟可能累积

**影响**: ⚠️ **中等影响** - 计算快但执行时机有问题

## 4. 性能瓶颈总结

### 高优先级问题
1. **`addPostFrameCallback` 延迟累积** ⚠️⚠️⚠️
   - 主线程阻塞时，延迟可达 590ms+
   - 导致滚动同步不流畅

2. **`ListView.separated` 频繁重建** ⚠️⚠️
   - 滚动时重建可见项
   - 每个 item 包含 `SelectableText`，布局计算较慢

### 中优先级问题
3. **`SelectableText` 布局计算** ⚠️
   - 长文本的布局计算可能较慢
   - 左侧原始文本和右侧分段都使用

4. **`MouseRegion` hover 重建** ⚠️
   - hover 时触发 `setState`，重建整个 item

## 5. 优化建议

### 立即优化
1. **减少 `addPostFrameCallback` 使用**
   - 考虑使用同步的 `jumpTo` 替代 `animateTo`（如果可接受）
   - 或者优化主线程性能，减少阻塞

2. **优化 `ListView` 性能**
   - 添加 `cacheExtent` 限制缓存范围
   - 使用 `RepaintBoundary` 包裹 item
   - 考虑使用 `SliverList`

3. **优化 `SelectableText`**
   - 使用 `RepaintBoundary` 包裹
   - 如果不需要选择，使用普通 `Text`

### 长期优化
4. **使用 `AutomaticKeepAliveClientMixin`**
   - 保持 item 状态，避免频繁重建

5. **虚拟化优化**
   - 考虑使用更高效的虚拟化列表组件

6. **主线程性能优化**
   - 减少不必要的 widget 重建
   - 优化复杂计算，使用 isolate


