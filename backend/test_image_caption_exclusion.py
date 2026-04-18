"""
Minimal tests for PDF exclusion detection: image vs image_caption.

This focuses on ensuring that image captions (text like "Figure 1: ...")
are NOT auto-excluded with exclusion_reason == "image".
"""

from exclusion.extractors.pdf_extractor import PDFMetadataExtractor
from exclusion.core.exclusion_detector import detect_exclusion_reason
from exclusion.core.exclusion_reason import ExclusionReason


def _build_extractor():
    # Block 0: pure image block
    # Block 1: image_caption block
    block_type_map = {
        0: "image",
        1: "image_caption",
    }
    block_image_map = {
        0: "images/img0.jpg",
    }
    return PDFMetadataExtractor(block_type_map=block_type_map, block_image_map=block_image_map)


def test_pure_image_segment_is_excluded_as_image():
    """
    A segment that is only an image placeholder should be excluded as IMAGE.
    """
    extractor = _build_extractor()
    segment_text = "<ph-img-0>"
    metadata = extractor.extract_metadata(
        segment_index=0,
        segment_text=segment_text,
        format_specific_data={
            "chunk_block_indices": [0],
        },
    )

    result = detect_exclusion_reason(
        text=segment_text,
        block_type=metadata.get("block_type"),
        target_lang="zh",
        is_image=metadata.get("is_image", False),
        is_table=metadata.get("is_table", False),
        strict_table_priority=True,  # PDF
    )

    assert result is not None
    reason, _ = result
    assert reason == ExclusionReason.IMAGE


def test_image_caption_segment_is_not_excluded_as_image():
    """
    A segment that contains an image placeholder PLUS caption text must NOT be
    auto-classified as IMAGE. It should be left for normal translation.
    """
    extractor = _build_extractor()
    segment_text = "<ph-img-0>\nFigure 1: Caption text for an image."
    metadata = extractor.extract_metadata(
        segment_index=1,
        segment_text=segment_text,
        format_specific_data={
            "chunk_block_indices": [1],
        },
    )

    # Sanity check: block_type reflects caption block, not plain "image"
    assert metadata.get("block_type") in ("image_caption", "caption", None)

    result = detect_exclusion_reason(
        text=segment_text,
        block_type=metadata.get("block_type"),
        target_lang="zh",
        is_image=metadata.get("is_image", False),
        is_table=metadata.get("is_table", False),
        strict_table_priority=True,  # PDF
    )

    # Caption should not be treated as IMAGE.
    if result is not None:
        reason, _ = result
        assert reason != ExclusionReason.IMAGE


if __name__ == "__main__":
    # Simple manual runner so this file can be executed directly.
    test_pure_image_segment_is_excluded_as_image()
    test_image_caption_segment_is_not_excluded_as_image()
    print("image/caption exclusion tests passed.")

