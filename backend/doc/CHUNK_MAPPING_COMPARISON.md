# Chunk Mapping Comparison: PDF vs DOCX/Excel

## 概述

本文档对比了 PDF 流程和 DOCX/Excel 流程中的 segment 到 chunk 映射逻辑，以及 `chunk_translation_helper.py` 的实现。

## PDF 流程的映射逻辑（已测试）

### 1. 构建阶段 (`_prepare_layout_preview_from_layout`)

**位置**: `backend/app/routes/app_routes_service.py:711-817`

```python
chunk_block_map = []
for idx, chunk in enumerate(layout_result.chunks):
    chunk_block_map.append(chunk.block_indices)  # chunk.block_indices 是 List[int]

task_state["layout_chunk_block_map"] = chunk_block_map
```

**特点**:
- `layout_chunk_block_map` 是一个 `List[List[int]]`，每个元素对应一个 chunk
- 每个元素 `chunk.block_indices` 是该 chunk 包含的 layout block 索引列表
- 这个映射在 `_prepare_layout_preview_from_layout` 中构建，用于 PDF 预览

### 2. 记录阶段 (`record_translation_segments`)

**位置**: `backend/utils/translation_segments.py:562-580`

```python
# Map segments to layout blocks if precomputed map is provided
if layout_chunk_block_map and segments:
    for idx, segment_dict in enumerate(segments):
        if idx >= len(layout_chunk_block_map):
            break
        block_indices = layout_chunk_block_map[idx] or []
        if block_indices:
            segment_dict["layout_block_indices"] = unique_indices
```

**特点**:
- 直接使用 `layout_chunk_block_map[idx]` 为 segment 设置 `layout_block_indices`
- 假设 `segments` 的索引与 `layout_chunk_block_map` 的索引一一对应
- 这个映射用于 PDF 渲染时，将翻译后的文本映射回 layout blocks

### 3. 关键点

- **PDF 流程中，segments 和 chunks 是一一对应的**（在 `_build_layout_markdown` 中，每个 chunk 对应一个 segment）
- `layout_chunk_block_map` 是 **chunk 索引到 layout block 索引的映射**
- 这个映射是**预计算的**，在 layout 解析阶段就确定了

## chunk_translation_helper.py 的映射逻辑

### 1. `translate_segments_with_chunking` 函数

**位置**: `backend/utils/chunk_translation_helper.py:195-380`

**构建的映射**:
```python
chunk_to_segment_map = []  # Maps chunk index to list of segment indices
for chunk_dict in chunks:
    segment_indices = [int(k) for k in sorted(chunk_dict.keys(), key=int)]
    chunk_to_segment_map.append(segment_indices)
```

**特点**:
- `chunk_to_segment_map` 是一个 `List[List[int]]`，每个元素对应一个 chunk
- 每个元素是该 chunk 包含的 segment 索引列表
- 这个映射用于将翻译后的 chunks 拆分回 segments

### 2. `translate_segments_with_agent` 函数

**位置**: `backend/utils/chunk_translation_helper.py:40-125`

**特点**:
- **没有构建任何映射**
- 只是保存 segments 到 `source_chunks_cache`
- 依赖 `SegmentsTranslateAgent.send_segments` 内部的映射逻辑

## 关键差异

### 1. 映射目的不同

| 映射 | PDF 流程 | DOCX/Excel 流程 |
|------|---------|----------------|
| `layout_chunk_block_map` | ✅ 用于 PDF 渲染（chunk → layout blocks） | ❌ 不适用 |
| `chunk_to_segment_map` | ❌ 不需要（segments 和 chunks 一一对应） | ✅ 用于拆分翻译后的 chunks 回 segments |

### 2. Segments 和 Chunks 的关系

- **PDF 流程**: segments 和 chunks **一一对应**（每个 chunk 对应一个 segment）
- **DOCX/Excel 流程**: chunks 可能包含**多个 segments**（通过 chunk merging）

### 3. 映射传递

- **PDF 流程**: `layout_chunk_block_map` 通过 `record_translation_segments` 的 `layout_chunk_block_map` 参数传递
- **DOCX/Excel 流程**: `chunk_to_segment_map` **没有被传递**给 `record_translation_segments`

## 发现的问题

### 1. `translate_segments_with_agent` 缺少映射传递

**问题**: `translate_segments_with_agent` 函数没有构建或传递 `chunk_to_segment_map`，这可能导致 `record_translation_segments` 无法正确映射 chunks 到 segments。

**影响**: 
- `record_translation_segments` 会使用内容匹配的方式重建映射（`translation_segments.py:265-349`）
- 这种方式可能不够准确，特别是当多个 segments 的内容相似时

### 2. `translate_segments_with_chunking` 的映射没有被使用

**问题**: `translate_segments_with_chunking` 函数构建了 `chunk_to_segment_map`，但这个映射只用于拆分翻译后的 chunks，**没有被传递给 `record_translation_segments`**。

**影响**:
- 如果后续需要记录 translation segments，映射信息会丢失
- 需要重新通过内容匹配来重建映射

## 建议的改进

### 1. 为 `translate_segments_with_agent` 添加映射传递

```python
def translate_segments_with_agent(
    segments: List[str],
    chunk_size: int,
    translate_agent: Any,
    ...
) -> Tuple[List[str], dict]:
    """
    Returns:
        Tuple containing:
        - translated_segments: List of translated segments
        - metadata: Dictionary with chunk_to_segment_map
    """
    # ... existing code ...
    
    # Build chunk_to_segment_map from SegmentsTranslateAgent's internal logic
    # This requires accessing the internal merged_indices_list
    # For now, we can save it to task_state for later use
    
    metadata = {
        "chunk_to_segment_map": chunk_to_segment_map,  # Need to extract from agent
    }
    
    return translated_segments, metadata
```

### 2. 修改 `record_translation_segments` 支持预计算的映射

```python
def record_translation_segments(
    ...
    chunk_to_segment_map: Optional[List[List[int]]] = None,  # Precomputed chunk to segment map
):
    # If chunk_to_segment_map is provided, use it directly
    # Otherwise, fall back to content-based matching
```

### 3. 在 DOCX/Excel translator 中传递映射

```python
# In DocxTranslator.translate_async
translated_segments, metadata = translate_segments_with_agent_async(...)
chunk_to_segment_map = metadata.get("chunk_to_segment_map")

record_translation_segments(
    ...
    chunk_to_segment_map=chunk_to_segment_map,  # Pass the precomputed map
)
```

## 测试状态

- ✅ **PDF 流程**: `layout_chunk_block_map` 映射逻辑已经过测试，用于 PDF 渲染
- ⚠️ **DOCX/Excel 流程**: `chunk_to_segment_map` 映射逻辑**尚未完全测试**，目前依赖内容匹配

## 结论

1. PDF 流程的映射逻辑是**经过测试的**，用于 PDF 渲染
2. DOCX/Excel 流程的映射逻辑**存在遗漏**：
   - `translate_segments_with_agent` 没有构建或传递 `chunk_to_segment_map`
   - `record_translation_segments` 需要依赖内容匹配来重建映射
3. **建议**: 修改 `translate_segments_with_agent` 和 `record_translation_segments` 以支持预计算的映射，提高准确性和性能

