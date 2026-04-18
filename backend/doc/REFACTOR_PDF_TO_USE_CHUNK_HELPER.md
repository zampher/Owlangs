# PDF Workflow 重构分析：统一使用 chunk_translation_helper

## 当前状态对比

### DOCX Workflow（已使用 helper）
```python
# backend/translator/ai_translator/docx_translator.py
translated_segments, metadata = translate_segments_with_agent(
    segments=texts_for_translation,
    chunk_size=self.chunk_size,
    translate_agent=self.translate_agent,  # SegmentsTranslateAgent
    task_id=task_id,
    task_state=task_state,
    ...
)
chunk_to_segment_map = metadata.get("chunk_to_segment_map")

record_translation_segments(
    ...
    chunk_to_segment_map=chunk_to_segment_map,
)
```

**特点**：
- ✅ 使用 `translate_segments_with_agent()` helper
- ✅ Helper 自动构建 `chunk_to_segment_map`
- ✅ Helper 自动保存 segments 到 `source_chunks_cache`
- ✅ 使用 `SegmentsTranslateAgent.send_segments()`（内部会合并 chunks）
- ✅ 返回已拆分的 `translated_segments`（每个 segment 对应一个翻译）

### PDF Workflow（未使用 helper）
```python
# backend/translator/ai_translator/md_translator.py
translated_text_chunks = await self.translate_agent.send_chunks_async(
    chunks_for_translation, progress_callback, chunk_size=self.chunk_size
)

# 手动记录 segments
record_translation_segments(
    task_id=task_id,
    source_chunks=chunks,  # 原文 chunks
    target_chunks=result,   # 译文 chunks
    ...
    layout_chunk_block_map=layout_map,  # PDF 特有的 layout block 映射
)
```

**特点**：
- ❌ 没有使用 helper
- ❌ 手动处理 chunks（需要处理 image chunks）
- ❌ 手动调用 `record_translation_segments()`
- ❌ 使用 `MDTranslateAgent.send_chunks_async()`（返回 chunks，不是 segments）
- ❌ 没有构建 `chunk_to_segment_map`（因为 PDF 中 chunks 和 segments 一一对应）

## 关键差异分析

### 1. Agent 接口差异

| 特性 | PDF (MDTranslateAgent) | DOCX (SegmentsTranslateAgent) |
|------|------------------------|-------------------------------|
| 方法 | `send_chunks()` / `send_chunks_async()` | `send_segments()` / `send_segments_async()` |
| 输入 | chunks (已合并的文本块) | segments (原始文本片段) |
| 输出 | chunks (已翻译的文本块) | segments (已翻译的片段，已拆分) |
| 内部处理 | 直接翻译 chunks | 先合并 segments → chunks，翻译后拆分回 segments |

### 2. Chunks 和 Segments 的关系

- **PDF**: chunks 和 segments **一一对应**（每个 chunk = 1 segment）
  - 原因：PDF 使用 `layout_prepared_chunks`，每个 chunk 对应一个 layout block
  - 不需要 `chunk_to_segment_map`（可以生成 `[[0], [1], [2], ...]` 的一对一映射）

- **DOCX**: chunks 可能包含**多个 segments**（通过 chunk merging）
  - 原因：DOCX 使用 `segments2json_chunks()` 合并小 segments 成大 chunks
  - 需要 `chunk_to_segment_map` 来正确映射

### 3. 特殊处理需求

**PDF 特有**：
- `layout_chunk_block_map`: 用于 PDF 渲染时映射回 layout blocks
- Image chunks: PDF 需要特殊处理 image placeholders
- `layout_prepared_chunks`: PDF 使用预准备的 chunks（来自 layout document）

**DOCX 特有**：
- 无特殊需求（相对简单）

## 重构方案

### 方案 A：扩展 helper 支持 `send_chunks`（推荐）

**优点**：
- ✅ 保持 PDF workflow 的现有逻辑（使用 `send_chunks`）
- ✅ 统一使用 helper，代码更易维护
- ✅ 自动处理 `chunk_to_segment_map`（即使是一对一映射）

**实现**：
```python
# backend/utils/chunk_translation_helper.py
def translate_chunks_with_agent(
    chunks: List[str],
    chunk_size: int,
    translate_agent: Any,  # MDTranslateAgent instance (send_chunks)
    task_id: Optional[str] = None,
    task_state: Optional[dict] = None,
    original_filename: Optional[str] = None,
    file_contents: Optional[bytes] = None,
    progress_callback: Optional[Callable] = None,
    layout_chunk_block_map: Optional[List[List[int]]] = None,  # PDF 特有
) -> Tuple[List[str], dict]:
    """
    Translate chunks using MDTranslateAgent (for PDF workflow).
    
    Similar to translate_segments_with_agent, but:
    - Uses send_chunks instead of send_segments
    - Assumes chunks and segments are one-to-one (for PDF)
    - Handles layout_chunk_block_map for PDF rendering
    """
    # Step 1: Build one-to-one chunk_to_segment_map (PDF assumption)
    chunk_to_segment_map = [[i] for i in range(len(chunks))]
    
    # Step 2: Save chunks to source_chunks_cache
    if task_state and task_id:
        # ... (same as translate_segments_with_agent)
    
    # Step 3: Translate using send_chunks
    if translate_agent:
        translated_chunks = await translate_agent.send_chunks_async(
            chunks, progress_callback, chunk_size=chunk_size
        )
    else:
        translated_chunks = chunks
    
    metadata = {
        "chunk_to_segment_map": chunk_to_segment_map,
        "layout_chunk_block_map": layout_chunk_block_map,  # Pass through for PDF
    }
    
    return translated_chunks, metadata
```

**使用**：
```python
# backend/translator/ai_translator/md_translator.py
from utils.chunk_translation_helper import translate_chunks_with_agent

translated_chunks, metadata = await translate_chunks_with_agent(
    chunks=chunks_for_translation,
    chunk_size=self.chunk_size,
    translate_agent=self.translate_agent,  # MDTranslateAgent
    task_id=task_id,
    task_state=task_state,
    layout_chunk_block_map=layout_chunk_block_map,
    ...
)

# 然后调用 record_translation_segments
record_translation_segments(
    ...
    chunk_to_segment_map=metadata.get("chunk_to_segment_map"),
    layout_chunk_block_map=metadata.get("layout_chunk_block_map"),
)
```

### 方案 B：统一使用 `send_segments`（不推荐）

**缺点**：
- ❌ PDF workflow 需要大幅修改（从 `send_chunks` 改为 `send_segments`）
- ❌ 可能影响 PDF 的 image placeholder 处理逻辑
- ❌ 需要验证 `SegmentsTranslateAgent` 是否支持 PDF 的特殊需求

## 推荐方案：方案 A

### 实施步骤

1. **扩展 `chunk_translation_helper.py`**
   - 添加 `translate_chunks_with_agent()` 函数
   - 支持 `send_chunks` / `send_chunks_async`
   - 处理 PDF 特有的 `layout_chunk_block_map`

2. **重构 `MDTranslator.translate_async()`**
   - 使用 `translate_chunks_with_agent()` 替换手动翻译逻辑
   - 简化代码，移除重复的 cache 保存逻辑
   - 保持 image chunk 处理逻辑

3. **统一 `record_translation_segments()` 调用**
   - PDF 和 DOCX 都通过 helper 获取 `chunk_to_segment_map`
   - 确保一致的错误处理和日志记录

### 预期收益

1. **代码维护性**：
   - ✅ 统一的 chunk/segment 处理逻辑
   - ✅ 减少重复代码
   - ✅ 更容易添加新功能（如 token 统计）

2. **一致性**：
   - ✅ PDF 和 DOCX 使用相同的 helper 模式
   - ✅ 统一的错误处理
   - ✅ 统一的日志记录

3. **可扩展性**：
   - ✅ 未来其他 workflow（如 Excel）也可以使用相同的 helper
   - ✅ 更容易添加新功能（如 chunk 级别的重试）

### 注意事项

1. **保持向后兼容**：
   - PDF workflow 的 `layout_chunk_block_map` 必须正确传递
   - Image chunks 的处理逻辑不能丢失

2. **测试验证**：
   - 确保 PDF 翻译结果不变
   - 确保 `layout_chunk_block_map` 正确映射
   - 确保 image placeholders 正确处理

3. **性能影响**：
   - Helper 会增加一层函数调用（可忽略）
   - 但会减少重复代码，提高可维护性

## 结论

**推荐重构**：方案 A（扩展 helper 支持 `send_chunks`）

**理由**：
- ✅ 统一代码结构，提高可维护性
- ✅ 保持 PDF workflow 的现有逻辑
- ✅ 最小化改动，降低风险
- ✅ 为未来扩展打下基础

**优先级**：中（不影响功能，但提高代码质量）

---

## 重构实施状态

**✅ 已完成**（2025-12-08）

### 实施内容

1. **扩展 `chunk_translation_helper.py`**
   - ✅ 添加 `translate_chunks_with_agent_async()` 函数
   - ✅ 支持 `send_chunks_async` 接口（PDF workflow）
   - ✅ 自动构建一对一 `chunk_to_segment_map`
   - ✅ 传递 `layout_chunk_block_map`（PDF 特有）

2. **重构 `MDTranslator.translate_async()`**
   - ✅ 使用 `translate_chunks_with_agent_async()` 替换手动翻译逻辑
   - ✅ 简化代码，移除重复的 cache 保存逻辑
   - ✅ 保持 image chunk 处理逻辑
   - ✅ 使用 helper 的 `chunk_to_segment_map` 传递给 `record_translation_segments()`

### 代码对比

**重构前**（~100 行手动处理）：
```python
# 手动调用 send_chunks_async
translated_text_chunks = await self.translate_agent.send_chunks_async(...)

# 手动处理 chunks 和 image placeholders
# 手动调用 record_translation_segments
record_translation_segments(...)
```

**重构后**（~30 行，使用 helper）：
```python
# 使用 helper
translated_text_chunks, metadata = await translate_chunks_with_agent_async(
    chunks=chunks_for_translation,
    chunk_size=self.chunk_size,
    translate_agent=self.translate_agent,
    task_id=task_id,
    task_state=task_state,
    layout_chunk_block_map=layout_chunk_block_map,
)

# Helper 自动处理 cache 和 mapping
# 只需调用 record_translation_segments 并传递 metadata
record_translation_segments(
    ...
    chunk_to_segment_map=metadata.get("chunk_to_segment_map"),
    layout_chunk_block_map=metadata.get("layout_chunk_block_map"),
)
```

### 收益

1. **代码简化**：PDF workflow 翻译逻辑从 ~100 行减少到 ~30 行
2. **统一性**：PDF 和 DOCX 现在都使用相同的 helper 模式
3. **可维护性**：统一的错误处理和日志记录
4. **可扩展性**：未来其他 workflow 也可以复用相同的 helper

### 注意事项

- ✅ 保持向后兼容：PDF workflow 的 `layout_chunk_block_map` 正确传递
- ✅ Image chunks 处理逻辑保持不变
- ✅ 错误处理：helper 失败时回退到直接翻译

