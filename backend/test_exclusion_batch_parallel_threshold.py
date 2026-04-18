from typing import List, Dict, Any, Tuple

import pytest

from backend.exclusion.detection.batch_detector import ExclusionDetectionBatch
from backend.exclusion.extractors.base import FormatMetadataExtractor


class _DummyMetadataExtractor(FormatMetadataExtractor):
    """Minimal metadata extractor for testing parallel threshold."""

    def extract_metadata(
        self,
        segment_index: int,
        segment_text: str,
        format_specific_data: dict | None = None,
    ) -> Dict[str, Any]:
        return {
            "block_type": "text",
            "is_table": False,
            "is_image": False,
            "is_header": False,
            "is_footer": False,
            "format_specific": {},
        }

    def get_format_name(self) -> str:
        return "pdf"


def _make_dummy_segments(n: int) -> List[str]:
    return [f"segment {i}" for i in range(n)]


def test_detect_exclusions_batch_uses_sequential_for_medium_batch(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    For medium-size batches (e.g. ~200 segments), we expect sequential processing
    to be used to avoid heavy ProcessPoolExecutor startup overhead on Windows.

    This test guards the threshold logic by ensuring that creating a
    ProcessPoolExecutor would raise if called; if the parallel path were taken,
    the test would fail.
    """
    import backend.exclusion.detection.batch_detector as batch_detector

    # Arrange: monkeypatch ProcessPoolExecutor to raise if used
    class _SentinelProcessPoolExecutor:  # type: ignore[override]
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            raise RuntimeError("ProcessPoolExecutor should not be used for medium batch sizes")

    monkeypatch.setattr(
        batch_detector,
        "ProcessPoolExecutor",
        _SentinelProcessPoolExecutor,
        raising=True,
    )

    # Medium-size batch similar to PDF example in logs
    segments = _make_dummy_segments(176)
    extractor = _DummyMetadataExtractor()
    task_state: Dict[str, Any] = {}

    # Act / Assert: should complete without trying to construct ProcessPoolExecutor
    excluded, detected = ExclusionDetectionBatch.detect_exclusions_batch(
        segments=segments,
        metadata_extractor=extractor,
        task_state=task_state,
        target_lang="en",
        preserve_existing=True,
        auto_exclude_optional=False,
    )

    # Basic sanity: result types
    assert isinstance(excluded, dict)
    assert isinstance(detected, dict)

