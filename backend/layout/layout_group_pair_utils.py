# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Shared helpers for multi-bbox layout group companions (Paddle column splits, etc.)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

LAYOUT_GROUP_PAIRS_KEY = "_layout_group_pairs"
LAYOUT_GROUP_PAIR_OF_KEY = "_layout_group_pair_of"
CROSS_PAGE_PAIR_OF_KEY = "_cross_page_pair_of"
LAYOUT_GROUP_TEXT_PARTS_KEY = "layout_group_text_parts"
LAYOUT_BLOCK_BBOX_OVERRIDES_KEY = "layout_block_bbox_overrides"


def parse_layout_group_text_parts(raw: Any) -> Optional[Dict[int, str]]:
    """Parse user-edited per-block text parts from segment metadata."""
    if raw is None:
        return None
    result: Dict[int, str] = {}
    if isinstance(raw, dict):
        for key, value in raw.items():
            if not isinstance(value, str):
                continue
            try:
                result[int(key)] = value
            except (TypeError, ValueError):
                continue
    elif isinstance(raw, list):
        for entry in raw:
            if not isinstance(entry, dict):
                continue
            idx_raw = entry.get("layout_block_index", entry.get("index"))
            text = entry.get("text")
            if not isinstance(text, str):
                continue
            try:
                result[int(idx_raw)] = text
            except (TypeError, ValueError):
                continue
    return result or None


def normalize_layout_group_text_parts(raw: Any) -> Optional[Dict[int, str]]:
    """Return trimmed parts dict or None when input is empty/invalid."""
    parsed = parse_layout_group_text_parts(raw)
    if not parsed:
        return None
    normalized = {
        idx: text.strip()
        for idx, text in parsed.items()
        if isinstance(text, str) and text.strip()
    }
    return normalized or None


def merge_layout_group_text_parts(
    parts: Dict[int, str],
    indices: Sequence[Any],
) -> str:
    """Join per-block texts in layout index order for segment target_text."""
    pieces: List[str] = []
    for raw_idx in indices:
        try:
            idx = int(raw_idx)
        except (TypeError, ValueError):
            continue
        text = (parts.get(idx) or "").strip()
        if text:
            pieces.append(text)
    return " ".join(pieces)


def layout_group_text_parts_cover_indices(
    parts: Dict[int, str],
    indices: Sequence[Any],
) -> bool:
    """True when parts include every required layout block index."""
    required: List[int] = []
    for raw_idx in indices:
        try:
            required.append(int(raw_idx))
        except (TypeError, ValueError):
            continue
    if len(required) < 2:
        return False
    return all(idx in parts for idx in required)


def serialize_layout_group_text_parts(parts: Dict[int, str]) -> Dict[str, str]:
    """Persist parts with string keys for JSON segment storage."""
    return {str(idx): text for idx, text in sorted(parts.items(), key=lambda item: item[0])}


def normalize_layout_block_bbox_override_entry(
    raw: Any,
) -> Optional[Tuple[float, float, float, float]]:
    """Parse a single [x0, y0, x1, y1] bbox override list."""
    if not isinstance(raw, (list, tuple)) or len(raw) < 4:
        return None
    try:
        return tuple(float(v) for v in raw[:4])
    except (TypeError, ValueError):
        return None


def parse_layout_block_bbox_overrides(
    raw: Any,
) -> Optional[Dict[int, Tuple[float, float, float, float]]]:
    """Parse per-layout-block bbox overrides from segment metadata."""
    if raw is None:
        return None
    result: Dict[int, Tuple[float, float, float, float]] = {}
    if isinstance(raw, dict):
        for key, value in raw.items():
            bbox = normalize_layout_block_bbox_override_entry(value)
            if bbox is None:
                continue
            try:
                result[int(key)] = bbox
            except (TypeError, ValueError):
                continue
    elif isinstance(raw, list):
        for entry in raw:
            if not isinstance(entry, dict):
                continue
            idx_raw = entry.get("layout_block_index", entry.get("index"))
            bbox = normalize_layout_block_bbox_override_entry(
                entry.get("bbox") or entry.get("layout_block_bbox_override"),
            )
            if bbox is None:
                continue
            try:
                result[int(idx_raw)] = bbox
            except (TypeError, ValueError):
                continue
    return result or None


def serialize_layout_block_bbox_overrides(
    overrides: Dict[int, Tuple[float, float, float, float]],
) -> Dict[str, list]:
    """Persist bbox overrides with string keys for JSON segment storage."""
    return {
        str(idx): [float(v) for v in bbox]
        for idx, bbox in sorted(overrides.items(), key=lambda item: item[0])
    }


def split_translated_text_for_layout_group_with_parts(
    segment: Optional[Dict[str, Any]],
    primary_index: int,
    primary_bbox: Tuple[float, float, float, float],
    translated_text: str,
    group_pairs: Sequence[Dict[str, Any]],
) -> Tuple[str, List[Dict[str, Any]]]:
    """Use stored layout_group_text_parts when complete; else area-proportional split."""
    parts = None
    if isinstance(segment, dict):
        parts = normalize_layout_group_text_parts(
            segment.get(LAYOUT_GROUP_TEXT_PARTS_KEY),
        )
        indices = segment.get("layout_block_indices") or []
        if parts and layout_group_text_parts_cover_indices(parts, indices):
            companion_specs: List[Dict[str, Any]] = []
            for pair in group_pairs:
                entry = _normalize_group_pair_entry(
                    index=pair.get("index"),
                    bbox=pair.get("bbox"),
                    page_index=pair.get("page_index"),
                )
                if entry is None:
                    continue
                try:
                    companion_idx = int(entry["index"])
                except (TypeError, ValueError):
                    continue
                text = (parts.get(companion_idx) or "").strip()
                if not text:
                    continue
                companion_specs.append(
                    {
                        "index": entry["index"],
                        "page_index": entry["page_index"],
                        "bbox": tuple(entry["bbox"]),
                        "text": text,
                    }
                )
            primary_text = (parts.get(int(primary_index)) or translated_text).strip()
            return primary_text, companion_specs
    return split_translated_text_for_layout_group(
        primary_bbox,
        translated_text,
        group_pairs,
    )


def is_layout_group_companion(raw: Any) -> bool:
    """True when block is an empty companion paired to a primary layout block."""
    return isinstance(raw, dict) and raw.get(LAYOUT_GROUP_PAIR_OF_KEY) is not None


def is_empty_layout_group_companion_of(
    companion_block: Any,
    primary_block: Any,
) -> bool:
    """True when companion is a text-empty block explicitly paired to primary."""
    if companion_block is None or primary_block is None:
        return False
    companion_raw = getattr(companion_block, "raw", None) or {}
    if not is_layout_group_companion(companion_raw):
        return False
    pair_of = companion_raw.get(LAYOUT_GROUP_PAIR_OF_KEY)
    primary_index = getattr(primary_block, "index", None)
    if primary_index is None or pair_of is None:
        return False
    try:
        if int(pair_of) != int(primary_index):
            return False
    except (TypeError, ValueError):
        return False
    return not (getattr(companion_block, "text", None) or "").strip()


def is_cross_page_companion_block(raw: Any) -> bool:
    """True when block continues a paragraph from the previous page."""
    return isinstance(raw, dict) and raw.get(CROSS_PAGE_PAIR_OF_KEY) is not None


def is_layout_companion_block(raw: Any) -> bool:
    """True for cross-page or same-page group companion blocks."""
    if not isinstance(raw, dict):
        return False
    return is_cross_page_companion_block(raw) or is_layout_group_companion(raw)


def is_block_claimed_for_layout_group_pairing(raw: Any) -> bool:
    """True when block must not participate in same-page layout group pairing."""
    return is_layout_companion_block(raw)


def bbox_area(bbox: Sequence[float]) -> float:
    if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
        return 0.0
    try:
        x0, y0, x1, y1 = (float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3]))
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, x1 - x0) * max(0.0, y1 - y0)


def bbox_overlap_over_min_area(
    a: Sequence[float],
    b: Sequence[float],
) -> float:
    """Intersection area divided by min(area_a, area_b); 0 when no overlap."""
    if len(a) != 4 or len(b) != 4:
        return 0.0
    try:
        ax0, ay0, ax1, ay1 = (float(a[0]), float(a[1]), float(a[2]), float(a[3]))
        bx0, by0, bx1, by1 = (float(b[0]), float(b[1]), float(b[2]), float(b[3]))
    except (TypeError, ValueError):
        return 0.0
    ix0 = max(ax0, bx0)
    iy0 = max(ay0, by0)
    ix1 = min(ax1, bx1)
    iy1 = min(ay1, by1)
    if ix1 <= ix0 or iy1 <= iy0:
        return 0.0
    inter = (ix1 - ix0) * (iy1 - iy0)
    min_area = min(bbox_area(a), bbox_area(b))
    return inter / min_area if min_area > 0 else 0.0


def layout_group_ids_compatible(
    primary_group_id: Any,
    companion_group_id: Any,
) -> bool:
    """Reject companions whose Paddle group_id clearly belongs to another block."""
    if primary_group_id is None or companion_group_id is None:
        return True
    return primary_group_id == companion_group_id


def lookup_layout_block(
    layout_doc: Any,
    block_index: Any,
) -> Any:
    if layout_doc is None or block_index is None:
        return None
    try:
        target = int(block_index)
    except (TypeError, ValueError):
        return None
    for block in layout_doc.iter_blocks():
        if block.index is None:
            continue
        try:
            if int(block.index) == target:
                return block
        except (TypeError, ValueError):
            continue
    return None


def filter_valid_layout_group_pairs(
    primary_block: Any,
    pairs: Sequence[Dict[str, Any]],
    layout_doc: Any = None,
    *,
    duplicate_overlap_threshold: float = 0.85,
) -> List[Dict[str, Any]]:
    """Drop duplicate-bbox and group_id-mismatched companions."""
    primary_bbox = getattr(primary_block, "bbox", None)
    primary_raw = getattr(primary_block, "raw", None) or {}
    primary_gid = primary_raw.get("group_id") if isinstance(primary_raw, dict) else None

    kept: List[Dict[str, Any]] = []
    kept_bboxes: List[Tuple[float, float, float, float]] = []

    for pair in pairs:
        if not isinstance(pair, dict):
            continue
        entry = _normalize_group_pair_entry(
            index=pair.get("index"),
            bbox=pair.get("bbox"),
            page_index=pair.get("page_index"),
        )
        if entry is None:
            continue

        companion_bbox = tuple(entry["bbox"])
        if (
            isinstance(primary_bbox, (list, tuple))
            and len(primary_bbox) == 4
            and bbox_overlap_over_min_area(primary_bbox, companion_bbox)
            >= duplicate_overlap_threshold
        ):
            continue

        if any(
            bbox_overlap_over_min_area(seen, companion_bbox) >= duplicate_overlap_threshold
            for seen in kept_bboxes
        ):
            continue

        companion_gid = None
        companion_block = None
        if layout_doc is not None:
            companion_block = lookup_layout_block(layout_doc, entry.get("index"))
            if companion_block is not None:
                companion_raw = getattr(companion_block, "raw", None) or {}
                if isinstance(companion_raw, dict):
                    if is_cross_page_companion_block(companion_raw):
                        continue
                    companion_gid = companion_raw.get("group_id")
        if not layout_group_ids_compatible(primary_gid, companion_gid):
            continue
        if (
            companion_block is not None
            and isinstance(primary_bbox, (list, tuple))
            and len(primary_bbox) == 4
            and companion_block.bbox is not None
            and len(companion_block.bbox) == 4
            and is_same_row_parallel_column_pair(
                primary_bbox,
                companion_block.bbox,
            )
            and not is_empty_layout_group_companion_of(
                companion_block,
                primary_block,
            )
        ):
            continue

        kept.append(entry)
        kept_bboxes.append(companion_bbox)

    return kept


def sanitize_layout_group_pairs_on_document(layout_doc: Any) -> None:
    """Remove stale or invalid companion links after pairing heuristics run."""
    if layout_doc is None:
        return

    for block in layout_doc.iter_blocks():
        raw = block.raw if isinstance(block.raw, dict) else {}
        if not isinstance(raw, dict):
            continue
        pair_of = raw.get(LAYOUT_GROUP_PAIR_OF_KEY)
        if pair_of is None:
            continue
        if is_cross_page_companion_block(raw):
            cleaned = dict(raw)
            cleaned.pop(LAYOUT_GROUP_PAIR_OF_KEY, None)
            block.raw = cleaned
            continue
        primary = lookup_layout_block(layout_doc, pair_of)
        if primary is None:
            cleaned = dict(raw)
            cleaned.pop(LAYOUT_GROUP_PAIR_OF_KEY, None)
            block.raw = cleaned
            continue
        primary_raw = primary.raw if isinstance(primary.raw, dict) else {}
        if not layout_group_ids_compatible(
            primary_raw.get("group_id"),
            raw.get("group_id"),
        ):
            cleaned = dict(raw)
            cleaned.pop(LAYOUT_GROUP_PAIR_OF_KEY, None)
            block.raw = cleaned
            continue
        if (
            primary.bbox is not None
            and block.bbox is not None
            and bbox_overlap_over_min_area(primary.bbox, block.bbox) >= 0.85
        ):
            cleaned = dict(raw)
            cleaned.pop(LAYOUT_GROUP_PAIR_OF_KEY, None)
            block.raw = cleaned

    for block in layout_doc.iter_blocks():
        if not (block.text or "").strip():
            continue
        pairs = resolve_layout_group_pairs_for_block(block, layout_doc)
        raw = dict(block.raw or {})
        if pairs:
            raw[LAYOUT_GROUP_PAIRS_KEY] = pairs
        else:
            raw.pop(LAYOUT_GROUP_PAIRS_KEY, None)
        block.raw = raw


def bbox_y_overlap_ratio(
    a: Sequence[float],
    b: Sequence[float],
) -> float:
    if len(a) != 4 or len(b) != 4:
        return 0.0
    try:
        ay0, ay1 = float(a[1]), float(a[3])
        by0, by1 = float(b[1]), float(b[3])
    except (TypeError, ValueError):
        return 0.0
    inter = max(0.0, min(ay1, by1) - max(ay0, by0))
    union = max(ay1, by1) - min(ay0, by0)
    return inter / union if union > 0 else 0.0


def is_column_wrap_continuation_bbox(
    primary_bbox: Sequence[float],
    companion_bbox: Sequence[float],
    *,
    page_height: float = 842.0,
    x_gap_tol: float = 35.0,
    bottom_y_ratio: float = 0.38,
    top_y_ratio: float = 0.12,
) -> bool:
    """True when companion is top-of-right-column wrap from a bottom-left primary."""
    if len(primary_bbox) != 4 or len(companion_bbox) != 4:
        return False
    try:
        px0, py0, px1, py1 = (
            float(primary_bbox[0]),
            float(primary_bbox[1]),
            float(primary_bbox[2]),
            float(primary_bbox[3]),
        )
        ex0, ey0, ex1, ey1 = (
            float(companion_bbox[0]),
            float(companion_bbox[1]),
            float(companion_bbox[2]),
            float(companion_bbox[3]),
        )
    except (TypeError, ValueError):
        return False

    page_h = max(float(page_height), 1.0)
    if ex0 + x_gap_tol < px0:
        return False
    if px1 + x_gap_tol * 3 < ex0:
        return False
    if py0 < page_h * bottom_y_ratio:
        return False
    if ey1 > page_h * top_y_ratio:
        return False
    return True


def is_column_continuation_bbox(
    primary_bbox: Sequence[float],
    companion_bbox: Sequence[float],
    *,
    x_gap_tol: float = 35.0,
    min_y_overlap: float = 0.12,
    page_height: float = 842.0,
) -> bool:
    """True when companion looks like a right-column continuation of primary."""
    if is_column_wrap_continuation_bbox(
        primary_bbox,
        companion_bbox,
        page_height=page_height,
        x_gap_tol=x_gap_tol,
    ):
        return True
    if len(primary_bbox) != 4 or len(companion_bbox) != 4:
        return False
    try:
        px0, py0, px1, py1 = (
            float(primary_bbox[0]),
            float(primary_bbox[1]),
            float(primary_bbox[2]),
            float(primary_bbox[3]),
        )
        ex0, ey0, ex1, ey1 = (
            float(companion_bbox[0]),
            float(companion_bbox[1]),
            float(companion_bbox[2]),
            float(companion_bbox[3]),
        )
    except (TypeError, ValueError):
        return False

    if ex1 + x_gap_tol < px0:
        return False
    if px1 + x_gap_tol * 2 < ex0:
        return False

    x_adjacent = ex0 <= px1 + x_gap_tol and ex1 >= px0 - x_gap_tol
    if not x_adjacent:
        return False

    y_overlap = bbox_y_overlap_ratio(primary_bbox, companion_bbox)
    if y_overlap >= min_y_overlap:
        return True
    if ey0 <= py0 + (py1 - py0) * 0.35 and ey1 >= py0:
        return True
    return False


def _bbox_column_center_x(bbox: Sequence[float]) -> float:
    if len(bbox) != 4:
        return 0.0
    try:
        return (float(bbox[0]) + float(bbox[2])) / 2.0
    except (TypeError, ValueError):
        return 0.0


def is_left_column_bbox(
    bbox: Sequence[float],
    *,
    page_width: float = 595.0,
) -> bool:
    """True when bbox center lies in the left column of a two-column page."""
    return _bbox_column_center_x(bbox) <= page_width * 0.52


def is_right_column_bbox(
    bbox: Sequence[float],
    *,
    page_width: float = 595.0,
) -> bool:
    """True when bbox center lies in the right column of a two-column page."""
    return _bbox_column_center_x(bbox) >= page_width * 0.48


def paddle_group_cross_column_pair(
    primary_bbox: Sequence[float],
    companion_bbox: Sequence[float],
    *,
    page_width: float = 595.0,
) -> bool:
    """True when companion sits in the right column opposite a left-column primary."""
    if len(primary_bbox) != 4 or len(companion_bbox) != 4:
        return False
    if not is_left_column_bbox(primary_bbox, page_width=page_width):
        return False
    if not is_right_column_bbox(companion_bbox, page_width=page_width):
        return False
    try:
        px1 = float(primary_bbox[2])
        ex0 = float(companion_bbox[0])
    except (TypeError, ValueError):
        return False
    return ex0 >= px1 - 35.0


def is_same_row_parallel_column_pair(
    primary_bbox: Sequence[float],
    companion_bbox: Sequence[float],
    *,
    page_width: float = 595.0,
    min_y_overlap: float = 0.40,
    top_align_tol_ratio: float = 0.30,
) -> bool:
    """True when left/right blocks are independent paragraphs on the same row."""
    if len(primary_bbox) != 4 or len(companion_bbox) != 4:
        return False
    if not is_left_column_bbox(primary_bbox, page_width=page_width):
        return False
    if not is_right_column_bbox(companion_bbox, page_width=page_width):
        return False
    if bbox_y_overlap_ratio(primary_bbox, companion_bbox) < min_y_overlap:
        return False
    try:
        py0 = float(primary_bbox[1])
        ey0 = float(companion_bbox[1])
        ph = max(float(primary_bbox[3]) - py0, 1.0)
    except (TypeError, ValueError):
        return False
    return abs(py0 - ey0) <= ph * top_align_tol_ratio


def is_bottom_left_to_right_top_wrap_pair(
    primary_bbox: Sequence[float],
    companion_bbox: Sequence[float],
    *,
    page_height: float = 842.0,
    page_width: float = 595.0,
    vertical_gap_tol: float = 8.0,
) -> bool:
    """True when empty right-column top continues bottom-left primary (vertical reading order)."""
    del page_height  # reserved for future page-relative thresholds
    if len(primary_bbox) != 4 or len(companion_bbox) != 4:
        return False
    if is_same_row_parallel_column_pair(
        primary_bbox,
        companion_bbox,
        page_width=page_width,
    ):
        return False
    if not paddle_group_cross_column_pair(
        primary_bbox,
        companion_bbox,
        page_width=page_width,
    ):
        return False
    try:
        py0 = float(primary_bbox[1])
        ey0 = float(companion_bbox[1])
    except (TypeError, ValueError):
        return False
    # After reading the left column top-to-bottom, the right column resumes at the top.
    return ey0 + vertical_gap_tol < py0


def is_flow_column_continuation_bbox(
    primary_bbox: Sequence[float],
    companion_bbox: Sequence[float],
    *,
    page_height: float = 842.0,
    page_width: float = 595.0,
    min_y_overlap: float = 0.08,
) -> bool:
    """True for column-flow continuation (wrap/fill), not same-row parallel columns."""
    if is_same_row_parallel_column_pair(
        primary_bbox,
        companion_bbox,
        page_width=page_width,
    ):
        return False
    if is_column_wrap_continuation_bbox(
        primary_bbox,
        companion_bbox,
        page_height=page_height,
    ):
        return True
    if len(primary_bbox) != 4 or len(companion_bbox) != 4:
        return False
    if not is_left_column_bbox(primary_bbox, page_width=page_width):
        return False
    if not is_right_column_bbox(companion_bbox, page_width=page_width):
        return False
    try:
        py0 = float(primary_bbox[1])
        ey0 = float(companion_bbox[1])
    except (TypeError, ValueError):
        return False
    # Wrapped paragraph: right column block starts above the left block top.
    if ey0 + 8.0 < py0 and bbox_y_overlap_ratio(primary_bbox, companion_bbox) >= min_y_overlap:
        return True
    return False


def _nearest_whitespace_boundary(text: str, target: int) -> int:
    text_len = len(text)
    if target >= text_len:
        return text_len
    if text[target : target + 1].isspace():
        return target
    window = 20
    forward = next(
        (
            target + offset
            for offset in range(1, window)
            if target + offset < text_len and text[target + offset].isspace()
        ),
        None,
    )
    backward = next(
        (
            target - offset
            for offset in range(1, window)
            if target - offset > 0 and text[target - offset].isspace()
        ),
        None,
    )
    candidates = [pos for pos in (backward, forward) if pos is not None]
    if not candidates:
        return target
    return min(candidates, key=lambda pos: abs(pos - target))


def distribute_text_by_weights(text: str, weights: Sequence[float]) -> List[str]:
    """Split text across N slots proportionally to weights (word-boundary aware)."""
    weight_list = [max(float(w), 0.0) for w in weights]
    expected = len(weight_list)
    if expected == 0:
        return []
    normalized_text = (text or "").strip()
    if not normalized_text:
        return [""] * expected

    total_weight = sum(weight_list) or float(expected)
    text_len = len(normalized_text)
    result: List[str] = []
    cursor = 0
    for idx, weight in enumerate(weight_list):
        if idx == len(weight_list) - 1:
            result.append(normalized_text[cursor:].strip())
            break
        share = max(1, round(text_len * weight / total_weight))
        tentative_end = min(text_len, cursor + share)
        boundary = _nearest_whitespace_boundary(normalized_text, tentative_end)
        end_pos = max(boundary, cursor + 1)
        result.append(normalized_text[cursor:end_pos].strip())
        cursor = end_pos

    if len(result) < expected:
        result.extend([""] * (expected - len(result)))
    elif len(result) > expected:
        extra = result[expected - 1 :]
        merged = " ".join(piece for piece in extra if piece)
        result = result[: expected - 1] + [merged]
    return result


def split_text_by_bbox_areas(
    text: str,
    bboxes: Sequence[Sequence[float]],
) -> List[str]:
    """Split translated text across bbox regions by area ratio."""
    areas = [max(bbox_area(bbox), 1.0) for bbox in bboxes]
    return distribute_text_by_weights(text, areas)


def layout_group_pairs_from_raw(raw: Any) -> List[Dict[str, Any]]:
    if not isinstance(raw, dict):
        return []
    pairs = raw.get(LAYOUT_GROUP_PAIRS_KEY) or []
    if not isinstance(pairs, list):
        return []
    return [p for p in pairs if isinstance(p, dict)]


def _normalize_group_pair_entry(
    *,
    index: Any,
    bbox: Any,
    page_index: Any,
) -> Optional[Dict[str, Any]]:
    if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
        return None
    try:
        bbox_tuple = [float(v) for v in bbox[:4]]
    except (TypeError, ValueError):
        return None
    return {
        "index": index,
        "bbox": bbox_tuple,
        "page_index": page_index,
    }


def lookup_layout_block_bbox(
    layout_doc: Any,
    block_index: Any,
) -> Optional[Tuple[float, float, float, float]]:
    """Return the authoritative bbox for a layout block index."""
    if layout_doc is None or block_index is None:
        return None
    try:
        target = int(block_index)
    except (TypeError, ValueError):
        return None
    for block in layout_doc.iter_blocks():
        if block.index is None:
            continue
        try:
            if int(block.index) != target:
                continue
        except (TypeError, ValueError):
            continue
        bbox = getattr(block, "bbox", None)
        if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
            continue
        try:
            return tuple(float(v) for v in bbox[:4])
        except (TypeError, ValueError):
            return None
    return None


def bboxes_nearly_equal(
    a: Sequence[float],
    b: Sequence[float],
    *,
    tol: float = 0.5,
) -> bool:
    """Return True when two bboxes match within tolerance."""
    if len(a) != 4 or len(b) != 4:
        return False
    try:
        av = [float(v) for v in a[:4]]
        bv = [float(v) for v in b[:4]]
    except (TypeError, ValueError):
        return False
    return all(abs(left - right) <= tol for left, right in zip(av, bv))


def canonicalize_layout_group_pair_bbox(
    primary_bbox: Sequence[float],
    pair: Dict[str, Any],
    layout_doc: Any = None,
) -> Optional[Dict[str, Any]]:
    """Prefer companion block bbox from layout_doc over stale pair metadata."""
    entry = _normalize_group_pair_entry(
        index=pair.get("index"),
        bbox=pair.get("bbox"),
        page_index=pair.get("page_index"),
    )
    if entry is None:
        return None
    resolved = lookup_layout_block_bbox(layout_doc, entry.get("index"))
    if resolved is None:
        return entry
    stored = tuple(entry["bbox"])
    if bboxes_nearly_equal(stored, primary_bbox) or not bboxes_nearly_equal(stored, resolved):
        entry["bbox"] = [float(v) for v in resolved]
    return entry


def canonicalize_layout_group_pairs(
    primary_bbox: Sequence[float],
    pairs: Sequence[Dict[str, Any]],
    layout_doc: Any = None,
) -> List[Dict[str, Any]]:
    """Normalize companion pair entries and fix stale or primary-duplicated bboxes."""
    result: List[Dict[str, Any]] = []
    for pair in pairs:
        if not isinstance(pair, dict):
            continue
        entry = canonicalize_layout_group_pair_bbox(primary_bbox, pair, layout_doc)
        if entry is not None:
            result.append(entry)
    result.sort(
        key=lambda p: (
            int(p.get("page_index") or 0),
            float((p.get("bbox") or [0, 0, 0, 0])[1]),
            float((p.get("bbox") or [0, 0, 0, 0])[0]),
        )
    )
    return result


def resolve_layout_group_pairs_for_block(
    block: Any,
    layout_doc: Any = None,
) -> List[Dict[str, Any]]:
    """Return companion pair specs for a primary block (raw field or reverse lookup)."""
    raw = getattr(block, "raw", None) or {}
    pairs = layout_group_pairs_from_raw(raw)

    block_index = getattr(block, "index", None)
    if not pairs:
        if block_index is None or layout_doc is None:
            return []

        try:
            primary_index = int(block_index)
        except (TypeError, ValueError):
            return []

        companions: List[Dict[str, Any]] = []
        for other in layout_doc.iter_blocks():
            other_raw = getattr(other, "raw", None) or {}
            if not isinstance(other_raw, dict):
                continue
            if other_raw.get(LAYOUT_GROUP_PAIR_OF_KEY) != primary_index:
                continue
            if is_cross_page_companion_block(other_raw):
                continue
            if other.index is None or other.bbox is None or len(other.bbox) != 4:
                continue
            entry = _normalize_group_pair_entry(
                index=other.index,
                bbox=other.bbox,
                page_index=getattr(other, "page_index", None),
            )
            if entry is not None:
                companions.append(entry)

        pairs = companions

    primary_bbox = getattr(block, "bbox", None)
    if (
        pairs
        and layout_doc is not None
        and isinstance(primary_bbox, (list, tuple))
        and len(primary_bbox) == 4
    ):
        try:
            primary_tuple = tuple(float(v) for v in primary_bbox[:4])
        except (TypeError, ValueError):
            primary_tuple = None
        if primary_tuple is not None:
            pairs = canonicalize_layout_group_pairs(primary_tuple, pairs, layout_doc)
    return filter_valid_layout_group_pairs(block, pairs, layout_doc)


def split_translated_text_for_layout_group(
    primary_bbox: Tuple[float, float, float, float],
    translated_text: str,
    group_pairs: Sequence[Dict[str, Any]],
) -> Tuple[str, List[Dict[str, Any]]]:
    """Return (primary_portion, companion_specs with text) for a layout group."""
    if not group_pairs:
        return translated_text, []

    bboxes: List[Sequence[float]] = [primary_bbox]
    for pair in group_pairs:
        bbox = pair.get("bbox")
        if isinstance(bbox, (list, tuple)) and len(bbox) == 4:
            bboxes.append(bbox)

    if len(bboxes) <= 1:
        return translated_text, []

    portions = split_text_by_bbox_areas(translated_text, bboxes)
    primary_text = portions[0] if portions else translated_text
    companion_texts = portions[1:] if len(portions) > 1 else []

    companion_specs: List[Dict[str, Any]] = []
    for idx, pair in enumerate(group_pairs):
        entry = _normalize_group_pair_entry(
            index=pair.get("index"),
            bbox=pair.get("bbox"),
            page_index=pair.get("page_index"),
        )
        if entry is None:
            continue
        text = companion_texts[idx] if idx < len(companion_texts) else ""
        if not text.strip():
            continue
        companion_specs.append(
            {
                "index": entry["index"],
                "page_index": entry["page_index"],
                "bbox": tuple(entry["bbox"]),
                "text": text,
            }
        )
    return primary_text, companion_specs


CROSS_PAGE_PAIRS_KEY = "_cross_page_pairs"


def cross_page_pairs_from_raw(raw: Any) -> List[Dict[str, Any]]:
    """Return MinerU cross-page companion pair entries from a primary block raw dict."""
    if not isinstance(raw, dict):
        return []
    pairs = raw.get(CROSS_PAGE_PAIRS_KEY) or []
    if not isinstance(pairs, list):
        return []
    return [p for p in pairs if isinstance(p, dict)]


def _reading_order_key_for_block_index(
    layout_doc: Any,
    block_index: int,
) -> Tuple[int, float, float, int]:
    block = lookup_layout_block(layout_doc, block_index)
    if block is None:
        return (9999, 9999.0, 9999.0, block_index)
    page = getattr(block, "page_index", 0) or 0
    bbox = getattr(block, "bbox", None) or [0.0, 0.0, 0.0, 0.0]
    try:
        y0 = float(bbox[1])
        x0 = float(bbox[0])
    except (TypeError, ValueError):
        y0, x0 = 9999.0, 9999.0
    return (int(page), y0, x0, block_index)


def sort_layout_block_indices_reading_order(
    indices: Sequence[Any],
    layout_doc: Any,
    primary_index: Optional[Any] = None,
) -> List[int]:
    """Order layout block indices: primary first, companions by (page, y, x)."""
    ordered: List[int] = []
    seen: set[int] = set()
    for raw_idx in indices:
        try:
            idx = int(raw_idx)
        except (TypeError, ValueError):
            continue
        if idx in seen:
            continue
        ordered.append(idx)
        seen.add(idx)

    if not ordered:
        return []

    primary: Optional[int] = None
    if primary_index is not None:
        try:
            primary = int(primary_index)
        except (TypeError, ValueError):
            primary = None
    if primary is None:
        primary = ordered[0]

    companions = [idx for idx in ordered if idx != primary]
    companions.sort(
        key=lambda idx: _reading_order_key_for_block_index(layout_doc, idx),
    )
    if primary in seen:
        return [primary] + companions
    return companions


def resolve_overlay_layout_block_indices(
    segment: Optional[Dict[str, Any]],
    primary_block: Any,
    layout_doc: Any,
) -> List[int]:
    """Resolve ordered layout block indices for overlay text split (primary + companions)."""
    primary_index = getattr(primary_block, "index", None)
    try:
        primary_int = int(primary_index) if primary_index is not None else None
    except (TypeError, ValueError):
        primary_int = None

    indices: List[int] = []
    if isinstance(segment, dict):
        for raw_idx in segment.get("layout_block_indices") or []:
            try:
                indices.append(int(raw_idx))
            except (TypeError, ValueError):
                continue

    if primary_int is not None and primary_int in indices and len(indices) > 1:
        return sort_layout_block_indices_reading_order(
            indices,
            layout_doc,
            primary_int,
        )

    raw = getattr(primary_block, "raw", None) or {}
    pair_entries: List[Dict[str, Any]] = []
    for pair in cross_page_pairs_from_raw(raw):
        entry = _normalize_group_pair_entry(
            index=pair.get("index"),
            bbox=pair.get("bbox"),
            page_index=pair.get("page_index"),
        )
        if entry is not None:
            pair_entries.append(entry)
    for pair in resolve_layout_group_pairs_for_block(primary_block, layout_doc):
        entry = _normalize_group_pair_entry(
            index=pair.get("index"),
            bbox=pair.get("bbox"),
            page_index=pair.get("page_index"),
        )
        if entry is not None:
            pair_entries.append(entry)

    if not pair_entries and not indices:
        return [primary_int] if primary_int is not None else []

    merged: List[int] = []
    if primary_int is not None:
        merged.append(primary_int)
    for entry in pair_entries:
        try:
            companion = int(entry["index"])
        except (TypeError, ValueError, KeyError):
            continue
        if companion not in merged:
            merged.append(companion)
    for idx in indices:
        if idx not in merged:
            merged.append(idx)

    if len(merged) <= 1:
        return merged
    return sort_layout_block_indices_reading_order(
        merged,
        layout_doc,
        primary_int,
    )


def _block_spec_for_overlay_index(
    block_index: int,
    layout_doc: Any,
) -> Optional[Dict[str, Any]]:
    block = lookup_layout_block(layout_doc, block_index)
    if block is None:
        return None
    bbox = lookup_layout_block_bbox(layout_doc, block_index)
    if bbox is None:
        bbox_tuple = getattr(block, "bbox", None)
        if not isinstance(bbox_tuple, (list, tuple)) or len(bbox_tuple) != 4:
            return None
        try:
            bbox = tuple(float(v) for v in bbox_tuple[:4])
        except (TypeError, ValueError):
            return None
    page_index = getattr(block, "page_index", None)
    try:
        page_int = int(page_index) if page_index is not None else 0
    except (TypeError, ValueError):
        page_int = 0
    return {
        "index": block_index,
        "page_index": page_int,
        "bbox": bbox,
    }


def split_translated_text_for_overlay_blocks(
    segment: Optional[Dict[str, Any]],
    primary_block: Any,
    translated_text: str,
    layout_doc: Any,
) -> Dict[str, Any]:
    """Split translated text across all segment layout blocks (same-page + cross-page).

    Mirrors frontend ``resolveLayoutGroupDisplayTexts``: stored parts when complete,
    else area-proportional split in reading order (primary, then companions by page/y/x).
    """
    empty: Dict[str, Any] = {
        "main_text": translated_text,
        "main_bbox": None,
        "companion_specs": [],
        "used_segment_order": False,
    }
    if layout_doc is None or primary_block is None:
        return empty

    try:
        primary_index = int(getattr(primary_block, "index", 0))
    except (TypeError, ValueError):
        return empty

    indices = resolve_overlay_layout_block_indices(segment, primary_block, layout_doc)
    if len(indices) <= 1:
        return empty

    specs: List[Dict[str, Any]] = []
    for idx in indices:
        spec = _block_spec_for_overlay_index(idx, layout_doc)
        if spec is None:
            return empty
        specs.append(spec)

    parts = None
    if isinstance(segment, dict):
        parts = normalize_layout_group_text_parts(
            segment.get(LAYOUT_GROUP_TEXT_PARTS_KEY),
        )

    if parts and layout_group_text_parts_cover_indices(parts, indices):
        texts = [(parts.get(idx) or "").strip() for idx in indices]
    else:
        bboxes = [spec["bbox"] for spec in specs]
        texts = split_text_by_bbox_areas(translated_text, bboxes)
        texts = [(t or "").strip() for t in texts]

    primary_text = texts[0] if texts else translated_text
    companion_specs: List[Dict[str, Any]] = []
    for spec, text in zip(specs[1:], texts[1:]):
        if not text.strip():
            continue
        companion_specs.append(
            {
                "index": spec["index"],
                "page_index": spec["page_index"],
                "bbox": spec["bbox"],
                "text": text,
            }
        )

    return {
        "main_text": primary_text,
        "main_bbox": None,
        "companion_specs": companion_specs,
        "used_segment_order": True,
    }
