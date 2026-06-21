# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Typst Overlay PDF Renderer.

This is the main renderer that implements the high-fidelity PDF export
pipeline inspired by RetainPDF's overlay rendering architecture.

Pipeline Overview::

    Source PDF + LayoutDocument
           │
           ▼
    [1] source_cleanup.clean_source_pdf()
           │   PyMuPDF redaction on original text areas
           ▼
    [2] models.layout_block_to_render_block() × N
           │   Convert Owlangs LayoutBlock → RenderBlock
           ▼
    [3] font_fit.FontFitCalculator.calculate_fit_params()
           │   Compute font sizes, leading, fit parameters
           ▼
    [4] emitter.build_typst_overlay_source()
           │   Generate Typst source code
           ▼
    [5] compiler.TypstCompiler.compile_source()
           │   Run `typst compile` to produce overlay PDF
           ▼
    [6] overlay_merge.merge_overlay_pdf()
           │   Merge overlay PDF onto cleaned source PDF
           ▼
        Translated PDF (bytes)
"""

import io
import shutil
import time
import zipfile
from pathlib import Path
from typing import Dict, List, Optional
from tempfile import mkdtemp

from layout.base import LayoutDocument
from layout.pdf_renderer.base import BasePDFRenderer
from layout.pdf_renderer.config import PDFRendererConfig
from layout.pdf_renderer.typst_overlay.compiler import (
    TypstCompiler, is_typst_available, TypstCompileError,
)
from layout.pdf_renderer.typst_overlay.emitter import (
    build_typst_overlay_source,
    build_typst_background_source,
)
from layout.pdf_renderer.typst_overlay.models import (
    RenderBlock, RenderPageSpec, layout_block_to_render_block,
)
from layout.pdf_renderer.typst_overlay.font_fit import (
    FontFitCalculator,
    is_ref_text_layout,
)
from layout.pdf_renderer.typst_overlay.segment_font_metrics import (
    apply_user_font_override,
    apply_user_typography_override,
)
from layout.pdf_renderer.typst_overlay.source_cleanup import (
    clean_source_pdf, PYMUPDF_AVAILABLE as _pymupdf_ok,
)
from layout.pdf_renderer.typst_overlay.overlay_merge import (
    merge_overlay_pdf,
    patch_merged_pdf_pages,
    patch_merged_pdf_pages_from_rendered,
)
from layout.pdf_renderer.typst_overlay.visual_images import (
    collect_visual_image_placements,
    lookup_image_bytes,
    extract_equation_image_path,
)
from layout.block_types import (
    EQUATION_BLOCK_TYPES,
    TABLE_CAPTION, IMAGE_CAPTION, CHART_CAPTION, CAPTION,
    TABLE_FOOTNOTE, CHART_BODY,
)
from layout.pdf_renderer.shared.block_processor import BlockProcessor
from logger.logger import unified_logger, LogModule


# Availability flags
TYPST_OVERLAY_AVAILABLE = is_typst_available() and _pymupdf_ok

if not _pymupdf_ok:
    _typst_overlay_import_error = "PyMuPDF (fitz) is required"
elif not is_typst_available():
    _typst_overlay_import_error = "Typst CLI is not installed or not in PATH"
else:
    _typst_overlay_import_error = None

# Platform-appropriate default font family for Typst
import platform as _platform
_sys = _platform.system()
if _sys == "Windows":
    DEFAULT_TYPST_FONT = "Microsoft YaHei"
elif _sys == "Darwin":
    DEFAULT_TYPST_FONT = "PingFang SC"
else:
    DEFAULT_TYPST_FONT = "Noto Sans SC"


class TypstOverlayRenderer(BasePDFRenderer):
    """
    High-fidelity PDF renderer using Typst overlay.

    This renderer preserves the original PDF's visual structure while
    replacing text with translations. It uses:

    - PyMuPDF to clean original text from source pages
    - Typst (via CLI) to generate precisely positioned overlay pages
    - PyMuPDF show_pdf_page() to merge the overlay

    Usage::

        config = PDFRendererConfig(
            translated_text_by_block_index=block_text_map,
            zip_bytes=zip_bytes,
            source_pdf_path="/path/to/original.pdf",
        )
        renderer = TypstOverlayRenderer(config)
        pdf_bytes = renderer.render(layout_doc)
    """

    def __init__(self, config: PDFRendererConfig):
        """
        Initialize the Typst overlay renderer.

        Args:
            config: Renderer configuration (must have source_pdf_path set)

        Raises:
            ImportError: If required dependencies (Typst CLI, PyMuPDF) are not available
        """
        if not _pymupdf_ok:
            raise ImportError(
                "PyMuPDF (fitz) is required for Typst overlay rendering. "
                "Install with: pip install PyMuPDF"
            )
        if not is_typst_available():
            raise ImportError(
                "Typst CLI is required for Typst overlay rendering. "
                "Install from: https://github.com/typst/typst/releases"
            )

        super().__init__(config)

        # Initialize sub-components
        self._compiler = TypstCompiler()
        self._font_fit = FontFitCalculator()

        # Resolve source PDF path
        self._source_pdf_path: Optional[Path] = None
        if hasattr(config, 'source_pdf_path') and config.source_pdf_path:
            raw = config.source_pdf_path
            if isinstance(raw, (str, Path)):
                self._source_pdf_path = Path(raw)
                if not self._source_pdf_path.exists():
                    unified_logger.warning(
                        LogModule.RESTOR,
                        f"[TYPST_OVERLAY] Source PDF not found: {self._source_pdf_path}"
                    )
                    self._source_pdf_path = None

        # Typst font family
        self._font_family = getattr(config, 'typst_font_family', None) or DEFAULT_TYPST_FONT

        # Output path (debug)
        self._output_path = getattr(config, 'output_path', None)

    @staticmethod
    def _is_image_based_pdf(pdf_path: Path, coverage_threshold: float = 0.6) -> bool:
        """
        Detect if the PDF is image-based (scanned / single large image per page).

        Returns True if any page has a single image whose area covers >=
        ``coverage_threshold`` of the page area.  Such PDFs cannot use the
        redaction-based overlay approach because there are no text objects
        to redact — all content is baked into a raster image.

        Args:
            pdf_path: Path to the PDF file.
            coverage_threshold: Fraction of page area the image must cover.
        """
        import fitz
        doc = fitz.open(pdf_path)
        try:
            for page_idx in range(len(doc)):
                page = doc[page_idx]
                images = page.get_images(full=True)
                if len(images) != 1:
                    continue
                xref = images[0][0]
                try:
                    pix = fitz.Pixmap(doc, xref)
                    img_area = pix.width * pix.height
                    pix = None
                except Exception:
                    continue
                # Scale image pixels to page coordinates
                page_rect = page.rect
                page_area = page_rect.width * page_rect.height
                if page_area <= 0:
                    continue
                coverage = img_area / page_area
                if coverage >= coverage_threshold:
                    unified_logger.info(
                        LogModule.RESTOR,
                        f"[TYPST_OVERLAY] Image-based PDF detected: "
                        f"page {page_idx} has 1 image covering "
                        f"{coverage:.0%} of page area ({images[0][2]}x{images[0][3]}px). "
                        f"Will use background-embed mode."
                    )
                    return True
        finally:
            doc.close()
        return False

    def _resolve_cross_page_target(
        self,
        block_page_index: int,
        cross_bbox: tuple,
        layout_doc: LayoutDocument,
    ) -> int:
        """Determine the actual page index for a cross-page line's bbox.

        The default assumption is that cross-page lines land on
        ``block_page_index + 1``.  However, when a paragraph spans
        two pages with intervening content (images, tables) that take
        up a full page, the cross-page line may actually land on
        ``block_page_index + 2`` or further.

        This method uses the LayoutDocument's page heights to resolve
        the correct target page by checking whether the bbox's y
        coordinates fall within each successive page's coordinate
        space.
        """
        x0, y0, x1, y1 = cross_bbox
        page_height = None
        for page in layout_doc.pages:
            if page.page_index == block_page_index:
                page_height = page.height
                break
        if page_height is None or page_height <= 0:
            return block_page_index + 1

        # The cross-page line's bbox y-values are in the *next* page's
        # coordinate system (PDF pages each start at y=0).
        # A valid cross-page bbox should have y1 > 0 and y1 <= page_height.
        if 0 < y1 <= page_height:
            # bbox fits within a single page starting at y=0 → next page
            target = block_page_index + 1
        else:
            # Fallback: try successive pages
            target = block_page_index + 1
            for page in layout_doc.pages:
                if page.page_index <= block_page_index:
                    continue
                if page.height and 0 < y1 <= page.height:
                    target = page.page_index
                    break
                # If we encounter a page, any further pages would be even
                # less likely; break to avoid runaway loop.
                if page.page_index > block_page_index + 5:
                    break
        return target

    @staticmethod
    def _line_text_length(line: dict) -> int:
        spans = line.get("spans") or []
        return sum(len(str(s.get("content", ""))) for s in spans if isinstance(s, dict))

    @staticmethod
    def _move_trailing_punct(prev_text: str, next_text: str) -> tuple[str, str]:
        """Move leading punctuation from *next_text* to the end of *prev_text*.

        When translated text is split across pages, trailing punctuation
        (periods, commas, etc.) should stay with the preceding segment
        rather than appear at the start of the next segment.
        """
        trailing_punct = set(
            "。，、；：！？．…"      # 中文
            ".,;:!?"               # 英文
            "）》」』〕〉】"         # 右括号
            "'\"”’"                # 右引号
        )
        while next_text and next_text[0] in trailing_punct:
            prev_text += next_text[0]
            next_text = next_text[1:]
        return prev_text, next_text

    @staticmethod
    def _split_cross_page_text(block, translated_text: str) -> dict:
        """Detect cross-page lines in a block and split translated text proportionally.

        When a MinerU text block contains lines spanning two pages, the block's
        ``raw["lines"]`` array includes a line whose spans carry ``"cross_page": true``.
        The line's bbox belongs to the next page.  We compute the ratio of original
        text lengths for the main (on-page) lines vs. the cross-page lines, then split
        the *translated* text using that ratio to produce two portions.

        Returns:
            ``{
                "main_text": str,
                "main_bbox": tuple | None,  # bbox covering only the main (on-page) lines
                "cross_page_parts": [
                    {"block_id": str, "page_index": int, "bbox": tuple, "text": str},
                    ...
                ]
            }``

            If no cross-page lines are found, ``cross_page_parts`` is empty,
            ``main_text`` equals *translated_text*, and ``main_bbox`` is ``None``
            (caller should use the original block.bbox).
        """
        raw = getattr(block, "raw", None) or {}
        raw_lines = raw.get("lines") or []

        # Separate main lines from cross-page lines.
        # MinerU puts "cross_page": true on *spans* (not on lines).
        main_lines: list = []
        cross_page_lines: list = []
        for line in raw_lines:
            if not isinstance(line, dict):
                continue
            spans = line.get("spans") or []
            if any(isinstance(s, dict) and s.get("cross_page") for s in spans):
                cross_page_lines.append(line)
            else:
                main_lines.append(line)

        if not cross_page_lines:
            return {"main_text": translated_text, "main_bbox": None, "cross_page_parts": []}

        # Compute bbox area for each group (used to split translated text proportionally)
        def _bbox_area(bbox) -> float:
            if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
                return 0.0
            try:
                return (float(bbox[2]) - float(bbox[0])) * (float(bbox[3]) - float(bbox[1]))
            except (TypeError, ValueError):
                return 0.0

        main_area = sum(_bbox_area(ml.get("bbox")) for ml in main_lines)
        cross_area = sum(_bbox_area(cpl.get("bbox")) for cpl in cross_page_lines)
        total_area = main_area + cross_area

        page_index = getattr(block, "page_index", 0) or 0
        block_key = getattr(block, "index", 0)

        # Split by source character length (primary). Bbox area is a poor proxy when
        # (large area) while the cross-page tail is a short continuation (small area).
        main_len = sum(TypstOverlayRenderer._line_text_length(ml) for ml in main_lines)
        cross_len = sum(
            TypstOverlayRenderer._line_text_length(cpl) for cpl in cross_page_lines
        )
        total_len = main_len + cross_len
        if total_len > 0:
            ratio = main_len / total_len
        elif total_area > 0:
            ratio = main_area / total_area
        else:
            ratio = 0.7

        # Split translated text proportionally
        split_pos = max(1, round(len(translated_text) * ratio))
        main_text = translated_text[:split_pos].rstrip()
        cross_text = translated_text[split_pos:].lstrip()
        main_text, cross_text = TypstOverlayRenderer._move_trailing_punct(main_text, cross_text)

        # Build cross-page RenderBlock specs
        cross_page_parts: list = []
        if cross_text:
            cross_len = sum(TypstOverlayRenderer._line_text_length(cpl) for cpl in cross_page_lines)
            for i, cp_line in enumerate(cross_page_lines):
                cp_bbox = cp_line.get("bbox")
                if not isinstance(cp_bbox, list) or len(cp_bbox) != 4:
                    continue
                try:
                    lx0 = float(cp_bbox[0])
                    ly0 = float(cp_bbox[1])
                    lx1 = float(cp_bbox[2])
                    ly1 = float(cp_bbox[3])
                except (TypeError, ValueError):
                    continue
                # For single cross-page line, use full cross_text;
                # for multiple, distribute proportionally.
                if len(cross_page_lines) == 1:
                    line_text = cross_text
                else:
                    line_len = TypstOverlayRenderer._line_text_length(cp_line)
                    line_ratio = line_len / cross_len if cross_len > 0 else 1.0 / len(cross_page_lines)
                    line_pos = max(1, round(len(cross_text) * line_ratio))
                    line_text = cross_text[:line_pos].rstrip()
                    cross_text = cross_text[line_pos:].lstrip()
                    line_text, cross_text = TypstOverlayRenderer._move_trailing_punct(line_text, cross_text)
                cross_page_parts.append({
                    "block_id": f"block-{block_key}-cross-{i}",
                    "page_index": page_index + 1,
                    "bbox": (lx0, ly0, lx1, ly1),
                    "text": line_text,
                    "line_raw": cp_line,
                })

        # Compute the bbox covering only the main (on-page) lines
        main_bbox = None
        if main_lines:
            main_x0s, main_y0s, main_x1s, main_y1s = [], [], [], []
            for ml in main_lines:
                ml_bbox = ml.get("bbox")
                if isinstance(ml_bbox, list) and len(ml_bbox) == 4:
                    try:
                        main_x0s.append(float(ml_bbox[0]))
                        main_y0s.append(float(ml_bbox[1]))
                        main_x1s.append(float(ml_bbox[2]))
                        main_y1s.append(float(ml_bbox[3]))
                    except (TypeError, ValueError):
                        pass
            if main_x0s:
                main_bbox = (
                    min(main_x0s), min(main_y0s),
                    max(main_x1s), max(main_y1s),
                )

        return {"main_text": main_text, "main_bbox": main_bbox, "cross_page_parts": cross_page_parts}

    @staticmethod
    def _extract_caption_footnote_from_translated(merged_text: str):
        """Extract caption, body, and footnote from a merged table/image translation.

        The merged text typically has the structure::

            caption lines
            table body (markdown table / image placeholder / HTML table)
            footnote lines

        Returns:
            (caption_text, body_text, footnote_text) — each may be ``None``.
        """
        lines = merged_text.split('\n')

        # Locate table/image body boundaries
        body_start = None
        body_end = None
        for i, line in enumerate(lines):
            stripped = line.strip()
            if (
                stripped.startswith('|')
                or stripped.startswith('<ph-')
                or stripped.startswith('<table')
                or stripped.startswith('</table')
                or stripped.startswith('<img')
                or stripped.startswith('![')  # Markdown image syntax: ![alt](path)
            ):
                if body_start is None:
                    body_start = i
                body_end = i

        if body_start is None:
            # No body content — entire text may be caption only
            text = merged_text.strip()
            return (text if text else None, None, None)

        caption_parts = [l.strip() for l in lines[:body_start] if l.strip()]
        caption = '\n'.join(caption_parts) if caption_parts else None

        body_parts = [l.strip() for l in lines[body_start:body_end + 1] if l.strip()]
        body = '\n'.join(body_parts) if body_parts else None

        footnote_parts = [l.strip() for l in lines[body_end + 1:] if l.strip()]
        footnote = '\n'.join(footnote_parts) if footnote_parts else None

        return (caption, body, footnote)

    def _extract_caption_footnote_render_blocks(
        self,
        block,
        page_index: int,
    ) -> List[RenderBlock]:
        """Extract caption / footnote sub-blocks from an image/table block.

        Looks at ``raw["blocks"]`` for ``table_caption``, ``image_caption``,
        ``caption``, and ``table_footnote`` sub-blocks.  Returns RenderBlocks
        that carry the translated caption / footnote text with an opaque white
        fill to cover the original text on the source PDF.
        """
        block_type = getattr(block, 'type', '') or ''
        if block_type not in ('image', 'figure', 'table', 'chart'):
            return []

        raw = block.raw if hasattr(block, 'raw') else {}
        if not isinstance(raw, dict):
            return []

        nested_blocks = raw.get("blocks") or []
        if not nested_blocks:
            return []

        parent_index = block.index
        if parent_index is None:
            return []

        translated_text = ""
        if self.config.translated_text_by_block_index:
            translated_text = self.config.translated_text_by_block_index.get(parent_index, "")
        if not translated_text:
            return []

        caption_text, _body_text, footnote_text = self._extract_caption_footnote_from_translated(
            translated_text,
        )

        # Discover sub-block bboxes
        caption_bbox = None
        footnote_bboxes: list = []

        for sub in nested_blocks:
            if not isinstance(sub, dict):
                continue
            sub_type = str(sub.get("type", ""))
            sub_bbox = sub.get("bbox")
            if not isinstance(sub_bbox, (list, tuple)) or len(sub_bbox) != 4:
                continue
            try:
                sub_bbox_t = tuple(float(v) for v in sub_bbox)
            except (TypeError, ValueError):
                continue

            if sub_type in (TABLE_CAPTION, IMAGE_CAPTION, CHART_CAPTION, CAPTION):
                caption_bbox = sub_bbox_t
            elif sub_type == TABLE_FOOTNOTE:
                footnote_bboxes.append(sub_bbox_t)

        result: List[RenderBlock] = []

        # When an image placeholder precedes the caption text,
        # _extract_caption_footnote_from_translated treats the caption as a
        # footnote.  Fall back to footnote_text so the caption still renders.
        if not caption_text and footnote_text and caption_bbox:
            caption_text = footnote_text
            footnote_text = None

        if caption_text and caption_bbox:
            result.append(RenderBlock(
                block_id=f"caption-{parent_index}",
                page_index=page_index,
                inner_bbox=caption_bbox,
                markdown_text=caption_text,
                plain_text=caption_text,
                render_kind="plain_line" if len(caption_text) < 80 else "plain",
                font_size_pt=9.0,
                leading_em=1.3,
                font_weight="regular",
                text_color=(0.0, 0.0, 0.0),
                cover_fill=(1.0, 1.0, 1.0),
                use_cover_fill=False,
                opaque_fill=True,
                rotation=self._block_rotation(parent_index),
            ))

        if footnote_text and footnote_bboxes:
            for i, fn_bbox in enumerate(footnote_bboxes):
                result.append(RenderBlock(
                    block_id=f"footnote-{parent_index}-{i}",
                    page_index=page_index,
                    inner_bbox=fn_bbox,
                    markdown_text=footnote_text,
                    plain_text=footnote_text,
                    render_kind="plain_line" if len(footnote_text) < 80 else "plain",
                    font_size_pt=8.0,
                    leading_em=1.2,
                    font_weight="regular",
                    text_color=(0.0, 0.0, 0.0),
                    cover_fill=(1.0, 1.0, 1.0),
                    use_cover_fill=False,
                    opaque_fill=True,
                    rotation=self._block_rotation(parent_index),
                ))

        if result:
            unified_logger.debug(
                LogModule.RESTOR,
                f"[TYPST_OVERLAY] Extracted {len(result)} caption/footnote "
                f"render blocks from {block_type} block {parent_index} "
                f"(caption={bool(caption_text)}, footnote={bool(footnote_text)})"
            )

        return result

    def _load_image_data_map(self, layout_doc: LayoutDocument) -> Dict[str, bytes]:
        """Load MinerU layout images from ZIP bytes attached to config."""
        zip_bytes = getattr(self.config, "zip_bytes", None)
        if not zip_bytes:
            unified_logger.warning(
                LogModule.RESTOR,
                "[TYPST_OVERLAY] No layout ZIP bytes in config; "
                "chart/table image embedding unavailable (regular image blocks may still "
                "appear from the source PDF layer)",
            )
            return {}
        try:
            with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zip_file:
                return BlockProcessor.extract_all_images_from_layout(layout_doc, zip_file)
        except Exception as exc:
            unified_logger.warning(
                LogModule.RESTOR,
                f"[TYPST_OVERLAY] Failed to load images from layout ZIP: {exc}",
            )
            return {}

    @staticmethod
    def _collect_title_extension_redaction_rects(
        render_blocks_by_page: Dict[int, List[RenderBlock]],
    ) -> Dict[int, List[tuple]]:
        """Redact original text in the horizontal strip extended beyond layout bbox."""
        extra: Dict[int, List[tuple]] = {}
        for page_idx, blocks in render_blocks_by_page.items():
            for rb in blocks:
                target_w = rb.fit_target_width_pt
                if target_w <= 0:
                    continue
                x0, y0, x1, y1 = rb.inner_bbox
                base_w = x1 - x0
                if target_w <= base_w + 0.5:
                    continue
                extra.setdefault(page_idx, []).append(
                    (x1, y0, x0 + target_w, y1),
                )
        return extra

    def _append_visual_image_render_blocks(
        self,
        layout_doc: LayoutDocument,
        render_blocks_by_page: Dict[int, List[RenderBlock]],
        *,
        work_dir: Path,
        image_data_map: Dict[str, bytes],
    ) -> Dict[int, List[tuple]]:
        """Write chart/table/equation images and append image RenderBlocks. Returns extra redaction rects."""
        chart_fmt = getattr(self.config, "chart_body_format", "image") or "image"
        table_fmt = getattr(self.config, "table_body_format", "html") or "html"
        eq_fmt = getattr(self.config, "equation_format", "text") or "text"
        placements = collect_visual_image_placements(
            layout_doc,
            chart_body_format=chart_fmt,
            table_body_format=table_fmt,
            equation_format=eq_fmt,
            image_data_map=image_data_map,
        )
        if chart_fmt == "image":
            chart_count = sum(
                1 for page in layout_doc.pages for block in page.blocks if block.type == "chart"
            )
            if chart_count and not any(p.block_type == "chart" for p in placements):
                unified_logger.warning(
                    LogModule.RESTOR,
                    f"[TYPST_OVERLAY] layout has {chart_count} chart block(s) but 0 chart "
                    f"image placements (zip_images={len(image_data_map)}, "
                    f"check layout_source_zip and chart_body nested image_path)",
                )
        if eq_fmt.strip().lower() == "image":
            eq_count = sum(
                1
                for page in layout_doc.pages
                for block in page.blocks
                if block.is_equation()
            )
            if eq_count and not any(p.block_type == "equation" for p in placements):
                unified_logger.warning(
                    LogModule.RESTOR,
                    f"[TYPST_OVERLAY] layout has {eq_count} equation block(s) but 0 equation "
                    f"image placements (zip_images={len(image_data_map)}, "
                    f"check layout_source_zip and interline_equation image_path)",
                )
        if not placements:
            return {}

        images_dir = work_dir / "images"
        images_dir.mkdir(parents=True, exist_ok=True)
        extra_redaction: Dict[int, List[tuple]] = {}
        margin_pt = 2.0

        for placement in placements:
            image_bytes = lookup_image_bytes(image_data_map, placement.image_path)
            if not image_bytes:
                unified_logger.warning(
                    LogModule.RESTOR,
                    f"[TYPST_OVERLAY] Missing image bytes for {placement.block_type} "
                    f"block {placement.block_index}: {placement.image_path}",
                )
                continue

            filename = Path(placement.image_path).name
            dest_path = images_dir / filename
            if not dest_path.exists():
                dest_path.write_bytes(image_bytes)

            rel_path = f"images/{filename}"
            rb = RenderBlock(
                block_id=f"visual-{placement.block_type}-{placement.block_index}",
                page_index=placement.page_index,
                inner_bbox=placement.inner_bbox,
                render_kind="image",
                image_rel_path=rel_path,
            )
            render_blocks_by_page.setdefault(placement.page_index, []).append(rb)

            x0, y0, x1, y1 = placement.inner_bbox
            extra_redaction.setdefault(placement.page_index, []).append((
                max(0, x0 - margin_pt),
                max(0, y0 - margin_pt),
                x1 + margin_pt,
                y1 + margin_pt,
            ))
            unified_logger.info(
                LogModule.RESTOR,
                f"[TYPST_OVERLAY] Embedded {placement.block_type} image for block "
                f"{placement.block_index} on page {placement.page_index + 1}: "
                f"{filename}, bbox=({x0:.1f},{y0:.1f},{x1:.1f},{y1:.1f})",
            )

        return extra_redaction

    @staticmethod
    def _is_ref_text_block(block) -> bool:
        layout_raw = getattr(block, "raw", None) or {}
        return is_ref_text_layout(layout_raw, block_type=getattr(block, "type", "") or "")

    def _block_translated_text(self, block, block_key: int) -> str:
        translated = ""
        if self.config.translated_text_by_block_index:
            translated = self.config.translated_text_by_block_index.get(block_key, "")
        return translated or block.text or ""

    def _block_font_override_pt(self, block_key: int) -> Optional[float]:
        """Return user-specified font size for a layout block, if any."""
        overrides = getattr(self.config, "font_size_by_block_index", None) or {}
        if not overrides:
            return None
        value = overrides.get(block_key)
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _block_font_weight_override(self, block_key: int) -> Optional[str]:
        overrides = getattr(self.config, "font_weight_by_block_index", None) or {}
        if not overrides:
            return None
        value = overrides.get(block_key)
        return str(value) if value is not None else None

    def _block_font_style_override(self, block_key: int) -> Optional[str]:
        overrides = getattr(self.config, "font_style_by_block_index", None) or {}
        if not overrides:
            return None
        value = overrides.get(block_key)
        return str(value) if value is not None else None

    def _block_leading_override_em(self, block_key: int) -> Optional[float]:
        overrides = getattr(self.config, "leading_em_by_block_index", None) or {}
        if not overrides:
            return None
        value = overrides.get(block_key)
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _block_rotation(self, block_key: int) -> int:
        """Return user-specified rotation for a layout block, if any."""
        overrides = getattr(self.config, "rotation_by_block_index", None) or {}
        if not overrides:
            return 0
        value = overrides.get(block_key)
        if value is None:
            return 0
        try:
            rot = int(value)
            return rot if rot in {0, 90, 180, 270} else 0
        except (TypeError, ValueError):
            return 0

    def _apply_block_typography_overrides(
        self,
        rb: RenderBlock,
        block_key: int,
    ) -> RenderBlock:
        weight = self._block_font_weight_override(block_key)
        style = self._block_font_style_override(block_key)
        leading = self._block_leading_override_em(block_key)
        if weight is None and style is None and leading is None:
            return rb
        return apply_user_typography_override(
            rb,
            font_weight=weight,
            font_style=style,
            leading_em=leading,
        )

    def _collect_unified_ref_metrics(
        self,
        layout_doc: LayoutDocument,
    ) -> tuple[Optional[float], Optional[float]]:
        """Median per-block ref_text font size and leading across the document."""
        font_candidates: List[float] = []
        ref_blocks: list[tuple[RenderBlock, Any]] = []

        for page in layout_doc.pages:
            for block in page.blocks:
                if not block.has_text() or not self._is_ref_text_block(block):
                    continue
                block_key = block.index if block.index is not None else -1
                if self._block_font_override_pt(block_key) is not None:
                    continue
                translated = self._block_translated_text(block, block_key)
                if not translated.strip():
                    continue
                layout_raw = getattr(block, "raw", None) or {}
                rb = RenderBlock(
                    block_id=f"ref-est-{block_key}",
                    page_index=page.page_index,
                    inner_bbox=block.bbox,
                    plain_text=translated,
                    markdown_text=translated,
                )
                font_candidates.append(
                    self._font_fit.estimate_font_size(rb, layout_raw=layout_raw)
                )
                ref_blocks.append((rb, layout_raw))

        unified_font = self._font_fit.compute_unified_ref_font_size(font_candidates)
        unified_leading: Optional[float] = None
        if unified_font is not None:
            leading_candidates = [
                self._font_fit.estimate_ref_text_leading_em(
                    rb, unified_font, layout_raw=layout_raw,
                )
                for rb, layout_raw in ref_blocks
            ]
            unified_leading = self._font_fit.compute_unified_ref_leading_em(
                leading_candidates,
            )

        if unified_font is not None:
            leading_msg = (
                f", leading: {unified_leading:.2f}em"
                if unified_leading is not None
                else ""
            )
            unified_logger.info(
                LogModule.RESTOR,
                f"[TYPST_OVERLAY] Unified ref_text font: {unified_font:.1f}pt"
                f"{leading_msg} from {len(font_candidates)} bibliography block(s)",
            )
        return unified_font, unified_leading

    def render(self, layout_doc: LayoutDocument) -> bytes:
        """
        Render LayoutDocument to high-fidelity translated PDF.

        Args:
            layout_doc: Owlangs LayoutDocument with layout blocks and positions

        Returns:
            Translated PDF content as bytes

        Raises:
            RuntimeError: If no source PDF path is available
            TypstCompileError: If Typst compilation fails
        """
        started = time.perf_counter()
        diagnostics: dict = {}

        # ---- Step 0: Check prerequisites ----
        if self._source_pdf_path is None:
            raise RuntimeError(
                "source_pdf_path is required for TypstOverlayRenderer. "
                "Set PDFRendererConfig.source_pdf_path to the original PDF file."
            )

        # ---- Step 1: Build RenderBlocks from LayoutDocument ----
        build_started = time.perf_counter()
        render_blocks_by_page: Dict[int, List[RenderBlock]] = {}
        total_blocks = 0
        skipped_blocks = []  # [(block_index, block_type, image_path or "no-image")]
        eq_fmt = (getattr(self.config, "equation_format", "text") or "text").strip().lower()
        unified_ref_font_pt, unified_ref_leading_em = self._collect_unified_ref_metrics(
            layout_doc,
        )
        skip_overlay: set = getattr(self.config, "skip_overlay_block_indices", None) or set()

        for page in layout_doc.pages:
            blocks: List[RenderBlock] = []
            page_width_pt = (
                float(page.width) if getattr(page, "width", None) else None
            )
            for block in page.blocks:
                # Extract caption/footnote sub-blocks from image/table blocks
                # (these are nested in raw["blocks"] and normally skipped)
                caption_rbs = self._extract_caption_footnote_render_blocks(
                    block, page.page_index,
                )
                for rb in caption_rbs:
                    rb = self._font_fit.calculate_fit_params(
                        rb, page_width_pt=page_width_pt,
                    )
                    blocks.append(rb)
                    total_blocks += 1

                if eq_fmt == "image" and block.is_equation():
                    eq_img = extract_equation_image_path(block) or ""
                    skipped_blocks.append((
                        getattr(block, 'index', '?'),
                        getattr(block, 'type', '?'),
                        eq_img,
                        block.bbox,
                    ))
                    continue

                # If a table block has translated content, extract the table body
                # (markdown table) and create a RenderBlock for it.  The caption
                # and footnote are already extracted above as separate blocks.
                block_type = getattr(block, 'type', '') or ''
                if block_type == 'table':
                    block_key = block.index if block.index is not None else total_blocks
                    translated = ""
                    if self.config.translated_text_by_block_index:
                        translated = self.config.translated_text_by_block_index.get(block_key, "")
                    if translated:
                        _cap, table_body, _fn = self._extract_caption_footnote_from_translated(
                            translated,
                        )
                        if table_body and table_body.strip():
                            tb_rb = layout_block_to_render_block(
                                block,
                                page_index=page.page_index,
                                translated_text=table_body,
                                block_id=f"block-{block_key}",
                            )
                            tb_rb.opaque_fill = True
                            tb_rb = self._font_fit.calculate_fit_params(
                                tb_rb, page_width_pt=page_width_pt,
                            )
                            tb_rb = self._apply_block_typography_overrides(tb_rb, block_key)
                            tb_rb.rotation = self._block_rotation(block_key)
                            blocks.append(tb_rb)
                            total_blocks += 1

                    # Still skip (don't fall through to text handling) — the
                    # caption/footnote blocks above and the table body block here
                    # are the only overlay content for this table block.
                    skipped_blocks.append((
                        getattr(block, 'index', '?'),
                        getattr(block, 'type', '?'),
                        "table_overlay",
                        block.bbox,
                    ))
                    continue

                if not block.has_text():
                    # Log skipped blocks (images, tables, etc.)
                    _img = getattr(block, 'image_path', None) or ""
                    
                    # For chart blocks, also check nested raw data for image_path
                    if block.type == "chart" and not _img:
                        raw = getattr(block, 'raw', None) or {}
                        if isinstance(raw, dict):
                            nested_blocks = raw.get("blocks") or []
                            for sub in nested_blocks:
                                if isinstance(sub, dict) and sub.get("type") == CHART_BODY:
                                    for line in sub.get("lines") or []:
                                        if isinstance(line, dict):
                                            for span in line.get("spans") or []:
                                                if isinstance(span, dict) and span.get("image_path"):
                                                    _img = span.get("image_path")
                                                    break
                                        if _img:
                                            break
                                if _img:
                                    break
                    
                    skipped_blocks.append((
                        getattr(block, 'index', '?'),
                        getattr(block, 'type', '?'),
                        _img,
                        block.bbox,
                    ))
                    continue  # Skip image/table/chart blocks — they stay on original PDF

                # Use block.index (from MinerU layout) as the mapping key
                block_key = block.index if block.index is not None else total_blocks

                # Skip overlay for excluded or translation-failed segments:
                # don't erase original text and don't place overlay text.
                if block_key in skip_overlay:
                    skipped_blocks.append((
                        getattr(block, 'index', '?'),
                        getattr(block, 'type', '?'),
                        "skip_overlay",
                        block.bbox,
                    ))
                    continue

                translated = ""
                if self.config.translated_text_by_block_index:
                    translated = self.config.translated_text_by_block_index.get(block_key, "")
                if not translated:
                    translated = block.text or ""

                # Detect and split cross-page lines.
                # When a text block has lines marked "cross_page": true,
                # those lines render on the *next* page. We need to:
                #   1. Split the translated text proportionally
                #   2. Create a RenderBlock for the cross-page portion
                #      and place it in render_blocks_by_page[next_page].
                cross_page_info = self._split_cross_page_text(block, translated)
                main_text = cross_page_info["main_text"]
                main_bbox = cross_page_info.get("main_bbox")
                cross_page_parts = cross_page_info["cross_page_parts"]

                # Main block: render with the main portion of the translation.
                # When cross-page lines exist, use main_bbox (only the on-page
                # lines' bbox) so that font-size estimation is based on the
                # correct height, not the full paragraph bbox.
                rb = layout_block_to_render_block(
                    block,
                    page_index=page.page_index,
                    translated_text=main_text,
                    block_id=f"block-{block_key}",
                )
                if main_bbox is not None:
                    rb.inner_bbox = main_bbox
                layout_raw = getattr(block, "raw", None) or {}
                override_pt = self._block_font_override_pt(block_key)
                if override_pt is not None:
                    rb = apply_user_font_override(
                        rb,
                        override_pt,
                        calculator=self._font_fit,
                    )
                    ref_unified = None
                else:
                    ref_unified = (
                        unified_ref_font_pt
                        if self._is_ref_text_block(block)
                        else None
                    )
                    rb = self._font_fit.calculate_fit_params(
                        rb,
                        layout_raw=layout_raw,
                        ref_unified_font_pt=ref_unified,
                        ref_unified_leading_em=unified_ref_leading_em,
                        page_width_pt=page_width_pt,
                    )
                rb = self._apply_block_typography_overrides(rb, block_key)
                rb.rotation = self._block_rotation(block_key)
                blocks.append(rb)
                total_blocks += 1

                # Cross-page blocks: render on the target page.
                # _split_cross_page_text defaults to page_index+1, but
                # when intervening content (images, tables) fills an
                # entire page, the cross-page line may land further.
                # Use _resolve_cross_page_target to find the real page.
                for cp in cross_page_parts:
                    resolved_page = self._resolve_cross_page_target(
                        page.page_index, cp["bbox"], layout_doc,
                    )
                    cp_line_raw = cp.get("line_raw")
                    cp_layout_raw = (
                        {"lines": [cp_line_raw]} if isinstance(cp_line_raw, dict) else None
                    )
                    cp_bbox = cp["bbox"]
                    cp_height = max(1.0, cp_bbox[3] - cp_bbox[1])
                    cp_block = RenderBlock(
                        block_id=cp["block_id"],
                        page_index=resolved_page,
                        inner_bbox=cp_bbox,
                        markdown_text=cp["text"],
                        plain_text=cp["text"],
                        render_kind="plain_line" if len(cp["text"]) < 80 else "plain",
                        font_size_pt=rb.font_size_pt,
                        leading_em=rb.leading_em,
                        font_weight=rb.font_weight,
                        font_style=getattr(rb, "font_style", "normal"),
                        rotation=rb.rotation,
                        use_cover_fill=False,
                        opaque_fill=True,
                        cover_fill=(1.0, 1.0, 1.0),
                    )
                    if override_pt is not None:
                        cp_block = apply_user_font_override(
                            cp_block,
                            override_pt,
                            calculator=self._font_fit,
                        )
                    elif ref_unified is None:
                        cp_estimate = self._font_fit.estimate_font_size(
                            cp_block, layout_raw=cp_layout_raw,
                        )
                        cp_font_size = min(rb.font_size_pt, cp_estimate)
                        cp_block = RenderBlock(
                            **{
                                **cp_block.__dict__,
                                "font_size_pt": cp_font_size,
                            }
                        )
                    if override_pt is None:
                        cp_block = self._font_fit.calculate_fit_params(
                            cp_block,
                            preserve_font_size=ref_unified is None,
                            layout_raw=cp_layout_raw,
                            ref_unified_font_pt=ref_unified,
                            ref_unified_leading_em=unified_ref_leading_em,
                            page_width_pt=page_width_pt,
                        )
                    # Cross-page tails sit in a tight bbox; constrain height unless
                    # bibliography uses the document-wide fixed font size or user override.
                    if (
                        override_pt is None
                        and ref_unified is None
                        and not cp_block.fit_to_box
                    ):
                        cp_block = RenderBlock(
                            **{
                                **cp_block.__dict__,
                                "fit_to_box": True,
                                "fit_max_height_pt": cp_height * 0.9,
                                "fit_min_font_size_pt": max(
                                    self._font_fit.min_size_pt,
                                    cp_block.font_size_pt * 0.5,
                                ),
                            }
                        )
                    cp_block = self._apply_block_typography_overrides(cp_block, block_key)
                    render_blocks_by_page.setdefault(resolved_page, []).append(cp_block)
                    total_blocks += 1

            if blocks:
                # Use setdefault + extend so that cross-page RenderBlocks added
                # by a *previous* page's iteration are not overwritten.
                render_blocks_by_page.setdefault(page.page_index, []).extend(blocks)

        diagnostics["build_blocks_elapsed"] = time.perf_counter() - build_started
        unified_logger.info(
            LogModule.RESTOR,
            f"[TYPST_OVERLAY] Built {total_blocks} render blocks "
            f"across {len(render_blocks_by_page)} pages "
            f"in {diagnostics['build_blocks_elapsed']:.2f}s"
        )

        # Log all skipped (non-text) blocks — image blocks should remain on source PDF
        if skipped_blocks:
            unified_logger.info(
                LogModule.RESTOR,
                f"[TYPST_OVERLAY] Skipped {len(skipped_blocks)} non-text blocks "
                f"(images/tables should stay on original PDF):"
            )
            for idx, btype, img_path, bbox in skipped_blocks:
                unified_logger.info(
                    LogModule.RESTOR,
                    f"[TYPST_OVERLAY]   skip block_index={idx}, type={btype}, "
                    f"image={'YES: ' + img_path if img_path else 'no'}, "
                    f"bbox=({bbox[0]:.1f},{bbox[1]:.1f},{bbox[2]:.1f},{bbox[3]:.1f})"
                )

        if not render_blocks_by_page:
            unified_logger.warning(
                LogModule.RESTOR,
                "[TYPST_OVERLAY] No translatable text blocks found. "
                "Returning original PDF unchanged."
            )
            return self._source_pdf_path.read_bytes()

        # ---- Step 1b: Embed chart/table/equation images when format=image ----
        temp_dir = Path(mkdtemp(prefix="owlangs_typst_"))
        image_data_map = self._load_image_data_map(layout_doc)
        extra_redaction_rects = self._append_visual_image_render_blocks(
            layout_doc,
            render_blocks_by_page,
            work_dir=temp_dir,
            image_data_map=image_data_map,
        )
        title_extension_rects = self._collect_title_extension_redaction_rects(
            render_blocks_by_page,
        )
        if title_extension_rects:
            for page_idx, rects in title_extension_rects.items():
                extra_redaction_rects.setdefault(page_idx, []).extend(rects)

        # ---- Step 2: Clean source PDF ----
        # For image-based PDFs (scanned documents), redaction-based cleanup
        # is ineffective.  Use background-embed mode instead.
        is_image_based = self._is_image_based_pdf(self._source_pdf_path)

        unified_logger.info(
            LogModule.RESTOR,
            f"[TYPST_OVERLAY] Step 2: skip_overlay_block_indices="
            f"{sorted(skip_overlay) if skip_overlay else 'empty/None'}, "
            f"is_image_based={is_image_based}",
        )

        cleanup_started = time.perf_counter()
        try:
            cleaned_pdf_bytes = clean_source_pdf(
                self._source_pdf_path,
                layout_doc,
                merge_rects=True,
                extra_redaction_rects=extra_redaction_rects or None,
                skip_block_indices=skip_overlay or None,
            )
            diagnostics["cleanup_elapsed"] = time.perf_counter() - cleanup_started
        except Exception as e:
            unified_logger.warning(
                LogModule.RESTOR,
                f"[TYPST_OVERLAY] Source cleanup failed: {e}. "
                "Falling back to original PDF without cleanup."
            )
            cleaned_pdf_bytes = self._source_pdf_path.read_bytes()
            diagnostics["cleanup_elapsed"] = 0.0
            diagnostics["cleanup_error"] = str(e)

        cleaned_output = getattr(self.config, "cleaned_source_output_path", None)
        if cleaned_output is not None:
            cleaned_output = Path(cleaned_output)
            cleaned_output.parent.mkdir(parents=True, exist_ok=True)
            cleaned_output.write_bytes(cleaned_pdf_bytes)

        # ---- Step 3: Build PageSpecs ----
        specs_started = time.perf_counter()
        page_specs: List[RenderPageSpec] = []

        import fitz
        src_doc = fitz.open(stream=cleaned_pdf_bytes, filetype="pdf")
        _orig_doc = None
        try:
            # Diagnostic: compare cleaned PDF with original source dimensions
            try:
                _orig_doc = fitz.open(self._source_pdf_path)
            except Exception:
                pass

            page_keys = sorted(render_blocks_by_page.keys())
            render_only = getattr(self.config, "render_page_indices", None)
            if render_only is not None:
                page_keys = [k for k in page_keys if k in render_only]
            for page_idx in page_keys:
                if 0 <= page_idx < len(src_doc):
                    page = src_doc[page_idx]
                    spec = RenderPageSpec(
                        page_index=page_idx,
                        page_width_pt=float(page.rect.width),
                        page_height_pt=float(page.rect.height),
                        blocks=render_blocks_by_page[page_idx],
                    )
                    page_specs.append(spec)
                    # Compare cleaned vs original page dimensions
                    if _orig_doc and page_idx < len(_orig_doc):
                        _op = _orig_doc[page_idx]
                        _cw = float(page.rect.width)
                        _ch = float(page.rect.height)
                        _ow = float(_op.rect.width)
                        _oh = float(_op.rect.height)
                        if abs(_cw - _ow) > 0.05 or abs(_ch - _oh) > 0.05:
                            unified_logger.warning(
                                LogModule.RESTOR,
                                f"[TYPST_OVERLAY] Page {page_idx} dims changed after cleanup: "
                                f"original=({_ow:.2f}, {_oh:.2f}) "
                                f"cleaned=({_cw:.2f}, {_ch:.2f}) "
                                f"delta=({_cw - _ow:+.2f}, {_ch - _oh:+.2f})",
                            )
        finally:
            src_doc.close()
            if _orig_doc:
                _orig_doc.close()

        diagnostics["build_specs_elapsed"] = time.perf_counter() - specs_started

        # ---- Step 3b: Image-based PDF → background-embed mode ----
        if is_image_based:
            unified_logger.info(
                LogModule.RESTOR,
                "[TYPST_OVERLAY] Using background-embed mode for image-based PDF "
                "(source page embedded as Typst background image)"
            )
            # Reuse temp_dir so table/chart images written in Step 1b remain on disk
            # for Typst image("images/...") references in overlay.typ.
            work_dir = temp_dir
            bg_typ_path = work_dir / "overlay.typ"
            bg_pdf_path = work_dir / "overlay.pdf"

            emit_started = time.perf_counter()
            src_pdf_in_workdir = work_dir / "source.pdf"
            shutil.copy2(self._source_pdf_path, src_pdf_in_workdir)
            typst_source = build_typst_background_source(
                page_specs,
                background_pdf_path=src_pdf_in_workdir,
                font_family=self._font_family,
                work_dir=work_dir,
            )
            diagnostics["emit_elapsed"] = time.perf_counter() - emit_started

            compile_started = time.perf_counter()
            bg_typ_path.write_text(typst_source, encoding="utf-8")
            try:
                self._compiler.compile(bg_typ_path, bg_pdf_path, phase="owlangs_overlay")
                if not bg_pdf_path.exists():
                    raise TypstCompileError(
                        phase="owlangs_overlay", stem="overlay",
                        typ_path=bg_typ_path, return_code=-1,
                        stderr="Compiled PDF file not found",
                    )
            except TypstCompileError:
                unified_logger.error(
                    LogModule.RESTOR,
                    "[TYPST_OVERLAY] Background-embed Typst compilation failed. "
                    f"Source at: {bg_typ_path}"
                )
                raise
            diagnostics["compile_elapsed"] = time.perf_counter() - compile_started

            # Read compiled PDF directly (no merge needed — source is background)
            final_pdf_bytes = bg_pdf_path.read_bytes()

            base_merged = getattr(self.config, "base_merged_pdf_bytes", None)
            render_only = getattr(self.config, "render_page_indices", None)
            if render_only is not None and base_merged is not None:
                if not page_specs:
                    unified_logger.warning(
                        LogModule.RESTOR,
                        "[TYPST_OVERLAY] Partial background-embed refresh has no "
                        "page specs; keeping cached PDF unchanged.",
                    )
                    return base_merged
                page_indices = [spec.page_index for spec in page_specs]
                final_pdf_bytes = patch_merged_pdf_pages_from_rendered(
                    base_merged,
                    final_pdf_bytes,
                    page_indices,
                )

            if self._output_path:
                self._output_path.parent.mkdir(parents=True, exist_ok=True)
                self._output_path.write_bytes(final_pdf_bytes)

            diagnostics["merge_elapsed"] = 0.0
            diagnostics["total_elapsed"] = time.perf_counter() - started
            unified_logger.info(
                LogModule.RESTOR,
                f"[TYPST_OVERLAY] Background-embed render complete in "
                f"{diagnostics['total_elapsed']:.2f}s "
                f"(blocks={total_blocks}, pages={len(page_specs)}, "
                f"cleanup={diagnostics.get('cleanup_elapsed', 0):.2f}s, "
                f"compile={diagnostics['compile_elapsed']:.2f}s)"
            )
            return final_pdf_bytes

        # ---- Step 4: Generate Typst source ----
        emit_started = time.perf_counter()
        typst_source = build_typst_overlay_source(page_specs, font_family=self._font_family)
        diagnostics["emit_elapsed"] = time.perf_counter() - emit_started

        # ---- Step 5: Compile Typst → overlay PDF ----
        compile_started = time.perf_counter()
        typ_path = temp_dir / "overlay.typ"
        pdf_path = temp_dir / "overlay.pdf"

        typ_path.write_text(typst_source, encoding="utf-8")

        try:
            self._compiler.compile(typ_path, pdf_path, phase="owlangs_overlay")
            if not pdf_path.exists():
                raise TypstCompileError(
                    phase="owlangs_overlay", stem="overlay",
                    typ_path=typ_path, return_code=-1,
                    stderr="Compiled PDF file not found",
                )
        except TypstCompileError:
            unified_logger.error(
                LogModule.RESTOR,
                "[TYPST_OVERLAY] Typst compilation failed. "
                f"Source at: {typ_path}"
            )
            # Save source for debugging
            if self._output_path:
                debug_typ = self._output_path.parent / f"{self._output_path.stem}_source.typ"
                debug_typ.write_text(typst_source, encoding="utf-8")
                unified_logger.info(
                    LogModule.RESTOR,
                    f"[TYPST_OVERLAY] Debug Typst source saved to {debug_typ}"
                )
            raise

        diagnostics["compile_elapsed"] = time.perf_counter() - compile_started

        # ---- Diagnostic: Compare compiled overlay page dims against specs ----
        _ovl_check_doc = fitz.open(pdf_path)
        try:
            _ovl_pages = len(_ovl_check_doc)
            _spec_pages = len(page_specs)
            if _ovl_pages != _spec_pages:
                unified_logger.warning(
                    LogModule.RESTOR,
                    f"[TYPST_OVERLAY] Compiled page count mismatch: "
                    f"specs={_spec_pages} overlay_pdf={_ovl_pages}",
                )
            for _sp in page_specs:
                _pi = _sp.page_index
                if _pi < _ovl_pages:
                    _op = _ovl_check_doc[_pi]
                    _ow = float(_op.rect.width)
                    _oh = float(_op.rect.height)
                    _dw = _ow - _sp.page_width_pt
                    _dh = _oh - _sp.page_height_pt
                    if abs(_dw) > 0.05 or abs(_dh) > 0.05:
                        unified_logger.warning(
                            LogModule.RESTOR,
                            f"[TYPST_OVERLAY] Page {_pi}: spec=({_sp.page_width_pt:.2f}, "
                            f"{_sp.page_height_pt:.2f}) compiled=({_ow:.2f}, {_oh:.2f}) "
                            f"delta=({_dw:+.2f}, {_dh:+.2f})",
                        )
        finally:
            _ovl_check_doc.close()

        # ---- Step 6: Merge overlay onto cleaned PDF ----
        merge_started = time.perf_counter()
        base_merged = getattr(self.config, "base_merged_pdf_bytes", None)
        render_only = getattr(self.config, "render_page_indices", None)
        try:
            if render_only is not None and base_merged is not None:
                if not page_specs:
                    unified_logger.warning(
                        LogModule.RESTOR,
                        "[TYPST_OVERLAY] Partial overlay refresh has no page specs; "
                        "keeping cached PDF unchanged.",
                    )
                    final_pdf_bytes = base_merged
                else:
                    final_pdf_bytes = patch_merged_pdf_pages(
                        base_merged,
                        cleaned_pdf_bytes,
                        pdf_path,
                        [spec.page_index for spec in page_specs],
                    )
            else:
                final_pdf_bytes = merge_overlay_pdf(
                    cleaned_pdf_bytes,
                    pdf_path,
                    check_page_count=True,
                    compress=True,
                )
        except Exception as e:
            unified_logger.error(
                LogModule.RESTOR,
                f"[TYPST_OVERLAY] Overlay merge failed: {e}. "
                "Falling back to overlay PDF only."
            )
            final_pdf_bytes = pdf_path.read_bytes()
            diagnostics["merge_error"] = str(e)

        diagnostics["merge_elapsed"] = time.perf_counter() - merge_started

        # ---- Step 7: Save if requested ----
        if self._output_path:
            self._output_path.parent.mkdir(parents=True, exist_ok=True)
            self._output_path.write_bytes(final_pdf_bytes)

        diagnostics["total_elapsed"] = time.perf_counter() - started

        unified_logger.info(
            LogModule.RESTOR,
            f"[TYPST_OVERLAY] Render complete in {diagnostics['total_elapsed']:.2f}s "
            f"(blocks={total_blocks}, pages={len(page_specs)}, "
            f"cleanup={diagnostics.get('cleanup_elapsed', 0):.2f}s, "
            f"compile={diagnostics['compile_elapsed']:.2f}s)"
        )

        return final_pdf_bytes
