# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Extract font sizes from the original PDF to infer heading levels
for MinerU title blocks.

MinerU Cloud API layout.json spans do not include font size data,
so this module provides a fallback that reads font sizes directly
from the original PDF via PyMuPDF (fitz), matching text spans to
MinerU title blocks by bounding box position.
"""

import re
from typing import Any, Dict, List, Tuple, Optional
from dataclasses import dataclass

from layout.base import LayoutDocument, LayoutBlock
from logger import unified_logger as logger
from logger.logger import LogModule


@dataclass
class _TextSpan:
    """A single text span extracted from PDF with font information."""
    bbox: Tuple[float, float, float, float]
    size: float
    text: str


def pdf_has_text_layer(
    pdf_path: str,
    *,
    sample_pages: int = 5,
    min_chars_per_page: int = 40,
) -> bool:
    """
    Detect whether *pdf_path* is a digital PDF with a usable text layer.

    Samples up to *sample_pages* pages and returns True when the average
    extracted character count is at least *min_chars_per_page*. Scanned /
    image-only PDFs typically yield near-zero text.
    """
    try:
        import fitz
    except ImportError:
        logger.warning(
            LogModule.LAYOUT,
            "PyMuPDF not available, assuming no text layer",
        )
        return False

    try:
        pdf_doc = fitz.open(pdf_path)
    except Exception as exc:
        logger.warning(
            LogModule.LAYOUT,
            f"Failed to open PDF for text-layer detection: {exc}",
        )
        return False

    try:
        page_count = len(pdf_doc)
        if page_count <= 0:
            return False
        indices = list(range(min(page_count, max(1, sample_pages))))
        total_chars = 0
        for idx in indices:
            try:
                text = pdf_doc[idx].get_text("text") or ""
            except Exception:
                text = ""
            total_chars += len("".join(text.split()))
        avg_chars = total_chars / max(len(indices), 1)
        has_layer = avg_chars >= float(min_chars_per_page)
        logger.info(
            LogModule.LAYOUT,
            f"PDF text-layer detection: path={pdf_path}, "
            f"sampled={len(indices)}/{page_count}, avg_chars={avg_chars:.1f}, "
            f"has_text_layer={has_layer}",
        )
        return has_layer
    finally:
        pdf_doc.close()


def _block_mineru_span_font_size(block: LayoutBlock) -> float:
    """Return MinerU span.size for *block*, or 0 when unavailable."""
    raw = block.raw if isinstance(block.raw, dict) else {}
    if not raw:
        return 0.0
    try:
        from layout.mineru_layout_model import _get_max_span_font_size

        return float(_get_max_span_font_size(raw) or 0.0)
    except Exception:
        return 0.0


_TEXT_LIKE_BLOCK_TYPES = frozenset({
    "text",
    "title",
    "header",
    "footer",
    "list",
    "list_item",
    "ref_text",
    "footnote",
    "caption",
    "code",
    "table_caption",
    "image_caption",
    "figure_caption",
})


def annotate_layout_extracted_font_sizes(
    doc: LayoutDocument,
    pdf_path: str,
    *,
    force: bool = False,
) -> Dict[str, Any]:
    """
    Annotate layout blocks with extracted font sizes for digital PDFs.

    Priority per block:
      1. MinerU ``span.size`` (when present in block.raw)
      2. PyMuPDF text-layer span size matched by bbox overlap

    Writes ``extracted_font_size`` onto ``block.raw`` and records
    ``has_text_layer`` / annotation stats in ``doc.metadata``.
    """
    stats: Dict[str, Any] = {
        "has_text_layer": False,
        "annotated": 0,
        "from_mineru_span": 0,
        "from_pdf_text_layer": 0,
        "skipped": 0,
    }

    if not force and doc.metadata.get("extracted_font_sizes_applied"):
        stats["has_text_layer"] = bool(doc.metadata.get("has_text_layer"))
        stats["annotated"] = int(doc.metadata.get("extracted_font_sizes_count") or 0)
        return stats

    has_layer = pdf_has_text_layer(pdf_path)
    doc.metadata["has_text_layer"] = has_layer
    stats["has_text_layer"] = has_layer

    if not has_layer:
        doc.metadata["extracted_font_sizes_applied"] = True
        doc.metadata["extracted_font_sizes_count"] = 0
        logger.info(
            LogModule.LAYOUT,
            "Skipping extracted font-size annotation: scanned/image PDF "
            f"(no usable text layer): {pdf_path}",
        )
        return stats

    try:
        import fitz
    except ImportError:
        logger.warning(
            LogModule.LAYOUT,
            "PyMuPDF not available, cannot annotate extracted font sizes",
        )
        return stats

    try:
        pdf_doc = fitz.open(pdf_path)
    except Exception as exc:
        logger.warning(
            LogModule.LAYOUT,
            f"Failed to open PDF for font-size annotation: {exc}",
        )
        return stats

    try:
        for page in doc.pages:
            if page.page_index >= len(pdf_doc):
                continue
            text_spans = _extract_text_spans(pdf_doc[page.page_index])
            for block in page.blocks:
                block_type = (block.type or "").lower()
                if block_type and block_type not in _TEXT_LIKE_BLOCK_TYPES:
                    # Still allow blocks with text content even if type is unusual
                    if not block.has_text():
                        stats["skipped"] += 1
                        continue

                if not isinstance(block.raw, dict):
                    block.raw = {}

                existing = block.raw.get("extracted_font_size")
                if isinstance(existing, (int, float)) and float(existing) > 0:
                    stats["annotated"] += 1
                    continue

                span_size = _block_mineru_span_font_size(block)
                source = "mineru_span"
                size = span_size
                if size <= 0 and text_spans:
                    size = _match_max_font_size(block.bbox, text_spans)
                    source = "pdf_text_layer"

                if size <= 0:
                    stats["skipped"] += 1
                    continue

                block.raw["extracted_font_size"] = round(float(size), 2)
                block.raw["extracted_font_size_source"] = source
                stats["annotated"] += 1
                if source == "mineru_span":
                    stats["from_mineru_span"] += 1
                else:
                    stats["from_pdf_text_layer"] += 1
    finally:
        pdf_doc.close()

    doc.metadata["extracted_font_sizes_applied"] = True
    doc.metadata["extracted_font_sizes_count"] = stats["annotated"]
    logger.info(
        LogModule.LAYOUT,
        "Annotated extracted font sizes: "
        f"annotated={stats['annotated']} "
        f"(mineru={stats['from_mineru_span']}, "
        f"pdf={stats['from_pdf_text_layer']}), "
        f"skipped={stats['skipped']}, pdf={pdf_path}",
    )
    return stats


def ensure_layout_extracted_font_sizes(
    doc: Optional[LayoutDocument],
    pdf_path: Optional[str],
    *,
    enabled: bool = True,
) -> Dict[str, Any]:
    """Run annotation when *enabled* and inputs are valid; no-op otherwise."""
    if not enabled or doc is None or not pdf_path:
        return {
            "has_text_layer": False,
            "annotated": 0,
            "skipped_reason": "disabled_or_missing_inputs",
        }
    return annotate_layout_extracted_font_sizes(doc, str(pdf_path))


def resolve_prefer_extracted_pdf_font_size(
    task_state: Optional[Dict[str, Any]] = None,
) -> bool:
    """
    Read the user preference for preferring extracted digital-PDF font sizes.

    Defaults to True when unset / unreadable.
    """
    ctx = task_state or {}
    raw = ctx.get("prefer_extracted_pdf_font_size")
    if raw is None:
        raw = ctx.get("preferExtractedPdfFontSize")
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, (int, float)):
        return bool(raw)
    if isinstance(raw, str) and raw.strip():
        return raw.strip().lower() in ("1", "true", "yes", "on")

    owner = (ctx.get("owner_username") or "local").strip() or "local"
    try:
        from auth.user_profile import get_user_profile_manager

        profile = get_user_profile_manager().get_user_profile(owner)
        value = getattr(profile, "prefer_extracted_pdf_font_size", True)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in ("1", "true", "yes", "on")
        return bool(value)
    except Exception:
        return True


def infer_heading_levels_from_pdf(
    doc: LayoutDocument,
    pdf_path: str,
) -> None:
    """
    Use PyMuPDF to extract font sizes from the original PDF and infer
    heading levels for title blocks in the LayoutDocument.

    Matches MinerU title block bboxes to PDF text spans by position,
    then clusters font sizes to assign heading levels (H1 = largest).

    Args:
        doc: LayoutDocument with title blocks to update
        pdf_path: Path to the original PDF file
    """
    try:
        import fitz
    except ImportError:
        logger.warning(LogModule.LAYOUT,
            "PyMuPDF not available, skipping PDF font extraction")
        return

    try:
        pdf_doc = fitz.open(pdf_path)
    except Exception as e:
        logger.warning(LogModule.LAYOUT,
            f"Failed to open PDF for font extraction: {e}")
        return

    try:
        _process_document(doc, pdf_doc)
    finally:
        pdf_doc.close()


def _process_document(doc: LayoutDocument, pdf_doc) -> None:
    """
    Process all pages: extract PDF text spans, match to title blocks,
    and assign heading levels by clustering.
    """
    # Collect all title blocks across all pages, with their matched font sizes
    title_blocks: List[Tuple[LayoutBlock, float]] = []

    for page in doc.pages:
        if page.page_index >= len(pdf_doc):
            continue

        pdf_page = pdf_doc[page.page_index]

        # Extract text spans with font info from PDF page
        text_spans = _extract_text_spans(pdf_page)
        if not text_spans:
            continue

        # Match title blocks to PDF text spans
        for block in page.blocks:
            if not block.is_heading():
                continue

            max_font_size = _match_max_font_size(block.bbox, text_spans)
            if max_font_size > 0:
                title_blocks.append((block, max_font_size))

    if not title_blocks:
        logger.debug(LogModule.LAYOUT,
            "No title blocks matched to PDF text spans")
        return

    # P1: Filter out false-positive title blocks that are clearly body text.
    # MinerU sometimes classifies long paragraphs (abstract, intro body) as
    # "title" type. These should not receive heading markers.
    filtered: List[Tuple[LayoutBlock, float]] = []
    skipped = 0
    for block, fs in title_blocks:
        if _is_likely_heading(block):
            filtered.append((block, fs))
        else:
            skipped += 1
            # Reset to default (text will not get heading prefix)
            block.heading_level = 0

    if skipped:
        logger.info(LogModule.LAYOUT,
            f"Filtered out {skipped} false-positive title block(s) "
            f"based on content heuristics, keeping {len(filtered)} "
            f"for heading level assignment")

    if not filtered:
        logger.debug(LogModule.LAYOUT,
            "All title blocks were filtered out as false positives")
        return

    # Assign heading levels by clustering font sizes
    _assign_heading_levels(filtered)

    logger.info(LogModule.LAYOUT,
        f"Inferred heading levels for {len(title_blocks)} title blocks "
        f"from PDF font sizes")


def _extract_text_spans(pdf_page) -> List[_TextSpan]:
    """
    Extract text spans with font size info from a PDF page.

    Args:
        pdf_page: fitz.Page object

    Returns:
        List of _TextSpan with bbox, size, and text
    """
    import fitz
    spans: List[_TextSpan] = []

    try:
        page_dict = pdf_page.get_text("dict",
            flags=fitz.TEXT_PRESERVE_WHITESPACE | fitz.TEXT_PRESERVE_LIGATURES)
    except Exception:
        return spans

    for block in page_dict.get("blocks", []):
        if block.get("type") != 0:  # 0 = text block, skip images
            continue
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                bbox = span.get("bbox")
                size = span.get("size", 0.0)
                text = span.get("text", "")
                if bbox and len(bbox) == 4 and size > 0 and text.strip():
                    spans.append(_TextSpan(
                        bbox=tuple(bbox),
                        size=size,
                        text=text.strip(),
                    ))

    return spans


def _match_max_font_size(
    block_bbox: Tuple[float, float, float, float],
    text_spans: List[_TextSpan],
    overlap_threshold: float = 0.3,
) -> float:
    """
    Find the maximum font size among PDF text spans that overlap
    significantly with the given block bbox.

    Args:
        block_bbox: MinerU title block bbox (x0, y0, x1, y1)
        text_spans: PDF text spans with font info
        overlap_threshold: Minimum overlap ratio (span area) to consider a match

    Returns:
        Maximum font size found, or 0.0 if no match
    """
    bx0, by0, bx1, by1 = block_bbox
    max_size = 0.0

    for span in text_spans:
        sx0, sy0, sx1, sy1 = span.bbox

        # Quick rejection: no bbox overlap
        if sx1 <= bx0 or sx0 >= bx1 or sy1 <= by0 or sy0 >= by1:
            continue

        # Calculate overlap area
        ox0 = max(bx0, sx0)
        oy0 = max(by0, sy0)
        ox1 = min(bx1, sx1)
        oy1 = min(by1, sy1)

        if ox1 > ox0 and oy1 > oy0:
            overlap_area = (ox1 - ox0) * (oy1 - oy0)
            span_area = (sx1 - sx0) * (sy1 - sy0)
            if span_area > 0 and overlap_area / span_area >= overlap_threshold:
                if span.size > max_size:
                    max_size = span.size

    return max_size


def _is_likely_heading(block: LayoutBlock) -> bool:
    """
    Heuristic check to reject blocks that MinerU likely misclassified as titles.

    Real headings are typically short (one line, no sentence punctuation).
    Long body paragraphs and multi-sentence text are rejected.

    Args:
        block: A LayoutBlock with type == "title"

    Returns:
        True if the block looks like a real heading, False if it should be
        treated as body text (heading_level=0).
    """
    text = (block.text or "").strip()
    if not text:
        return False

    # Reject blocks that are too long — real headings don't exceed ~100 chars
    if len(text) > 100:
        return False

    # Reject multi-sentence blocks (Chinese "。" or English ". " with context)
    chinese_sentences = text.count("。")
    english_sentences = len(re.findall(r'\.\s+[A-Z]', text))
    if chinese_sentences > 1:
        return False
    if chinese_sentences == 1 and len(text) > 30:
        return False
    if english_sentences > 1:
        return False
    if english_sentences == 1 and len(text) > 50:
        return False

    # Reject blocks ending with sentence punctuation that are clearly body text
    if text.endswith((".", "。", "!", "！", "?", "？")):
        if len(text) > 40:
            return False
        # Also reject short "titles" ending in period (e.g. numbered list refs)
        if re.match(r'^[\d\s.]+$', text.rstrip(".。")):
            return False

    # Reject blocks with colon-only content like "Table 1:" or "Fig. 2:"
    # (these look like figure/table captions, not section headings)
    if re.match(r'^(Table|Figure|Fig|表|图)\s*\d+\s*[:\uFF1A]', text, re.IGNORECASE):
        return False

    return True


def _assign_heading_levels(
    title_blocks: List[Tuple[LayoutBlock, float]],
) -> None:
    """
    Assign heading levels to title blocks by clustering their font sizes.

    Uses adaptive clustering: finds natural gaps in font size distribution
    to determine heading hierarchy levels. Falls back to the font-size
    threshold mapping when clustering produces too few groups.

    Args:
        title_blocks: List of (LayoutBlock, font_size) tuples
    """
    if not title_blocks:
        return

    # Extract unique sorted font sizes
    font_sizes = sorted(set(fs for _, fs in title_blocks))

    if len(font_sizes) == 1:
        # Only one font size — all titles are the same level
        level = min(max(1, _absolute_level(font_sizes[0])), 6)
        for block, _ in title_blocks:
            block.heading_level = level
        return

    # Cluster font sizes by finding gaps large enough to warrant a level boundary
    # Use a gap threshold of 1.5pt (smaller than that is likely rendering noise)
    GAP_THRESHOLD = 1.5

    # Find gaps between consecutive sorted font sizes
    gaps = []
    for i in range(1, len(font_sizes)):
        gap = font_sizes[i] - font_sizes[i - 1]
        gaps.append((gap, i))  # (gap_size, index_of_upper_bound)

    # Sort gaps descending and determine how many clusters to create
    gaps.sort(key=lambda x: -x[0])

    # Decide cluster count: aim for 2-4 clusters, based on meaningful gaps
    # Only use gaps above the threshold
    significant_gaps = [g for g in gaps if g[0] >= GAP_THRESHOLD]

    if not significant_gaps:
        # All font sizes are too close — no reliable differentiation
        # Fall back to absolute level mapping
        _assign_by_absolute_thresholds(title_blocks)
        return

    # Use the top (size-1) significant gaps to create clusters (max 4 levels)
    max_levels = min(4, len(font_sizes))
    n_gaps = min(len(significant_gaps), max_levels - 1)

    # Use the n_gaps largest gaps to split
    split_indices = sorted(g[1] for g in significant_gaps[:n_gaps])

    # Assign heading levels based on which cluster each font size falls into
    # Largest font → H1, next → H2, etc.
    cluster_map = _build_cluster_map(font_sizes, split_indices)

    for block, fs in title_blocks:
        # Find the cluster index for this font size
        cluster_idx = _find_cluster(fs, cluster_map)
        level = min(cluster_idx + 1, 6)
        block.heading_level = level


def _build_cluster_map(
    font_sizes: List[float],
    split_indices: List[int],
) -> List[Tuple[float, float]]:
    """
    Build cluster boundaries from font sizes and split indices.

    Args:
        font_sizes: Sorted unique font sizes
        split_indices: Indices where clusters are split

    Returns:
        List of (lower_bound, upper_bound) for each cluster,
        sorted from largest to smallest (cluster 0 = H1 = largest fonts)
    """
    clusters = []
    prev_idx = 0
    for si in split_indices:
        cluster_sizes = font_sizes[prev_idx:si]
        if cluster_sizes:
            clusters.append((min(cluster_sizes), max(cluster_sizes)))
        prev_idx = si
    # Last cluster
    cluster_sizes = font_sizes[prev_idx:]
    if cluster_sizes:
        clusters.append((min(cluster_sizes), max(cluster_sizes)))

    # Sort by font size descending (largest first = H1)
    clusters.sort(key=lambda c: -c[1])
    return clusters


def _find_cluster(font_size: float, cluster_map: List[Tuple[float, float]]) -> int:
    """Find which cluster index a font size belongs to."""
    for idx, (lo, hi) in enumerate(cluster_map):
        if lo <= font_size <= hi:
            return idx
    # Fallback: nearest cluster
    best_idx = 0
    best_dist = float("inf")
    for idx, (lo, hi) in enumerate(cluster_map):
        mid = (lo + hi) / 2
        dist = abs(font_size - mid)
        if dist < best_dist:
            best_dist = dist
            best_idx = idx
    return best_idx


def _assign_by_absolute_thresholds(
    title_blocks: List[Tuple[LayoutBlock, float]],
) -> None:
    """
    Fallback: assign heading levels using absolute font size thresholds.
    """
    for block, fs in title_blocks:
        block.heading_level = min(max(1, _absolute_level(fs)), 6)


def _absolute_level(font_size: float) -> int:
    """
    Map font size to heading level using absolute thresholds.

    Thresholds are calibrated for typical academic/technical PDFs:
        >= 18pt  -> H1 (document title)
        >= 14pt  -> H2 (major section)
        >= 12pt  -> H3 (subsection)
        >= 10.5pt -> H4 (sub-subsection)
        >= 9pt   -> H5
        else     -> H6
    """
    if font_size >= 18.0:
        return 1
    elif font_size >= 14.0:
        return 2
    elif font_size >= 12.0:
        return 3
    elif font_size >= 10.5:
        return 4
    elif font_size >= 9.0:
        return 5
    else:
        return 6
