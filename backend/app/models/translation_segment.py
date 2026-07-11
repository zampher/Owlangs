# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Translation segment data model for structured storage of source and target text pairs.
"""

from dataclasses import dataclass, field
from typing import Optional
import time
import uuid


@dataclass
class TranslationSegment:
    """Single translation segment data structure."""
    
    segment_id: str  # Unique segment identifier (format: {task_id}_segment_{index})
    task_id: str  # Associated task ID
    segment_index: int  # Segment index in document (0-based)
    source_text: str  # Source text (original)
    target_text: str  # Target text (translated)
    source_length: int  # Source text character count
    target_length: int  # Target text character count
    status: str = "translated"  # Status: 'pending' | 'translated' | 'reviewed' | 'modified'
    reviewed: bool = False  # Whether segment has been reviewed
    modified: bool = False  # Whether segment has been manually modified
    modified_text: Optional[str] = None  # Manually modified text
    modified_by: Optional[str] = None  # Modifier identifier
    modified_at: Optional[float] = None  # Modification timestamp
    review_notes: Optional[str] = None  # Review notes
    created_at: float = field(default_factory=time.time)  # Creation timestamp
    
    # Format information (for Phase 4: output format restoration)
    source_format: Optional[str] = None  # Original file format: 'pdf', 'docx', 'txt', etc.
    workflow_type: Optional[str] = None  # Workflow type used: 'markdown_based', 'docx', etc.
    
    # Platform and failure tracking (for retry mechanism)
    platform_used: Optional[str] = None  # AI platform key used for translation (e.g., 'openai', 'doubao')
    is_failed: bool = False  # Whether translation failed (auto-detected or manual)
    failure_reason: Optional[str] = None  # Failure reason if translation failed
    needs_retry: bool = False  # Whether user manually marked for retry
    retry_count: int = 0  # Number of retry attempts
    used_platforms: list[str] = field(default_factory=list)  # List of platforms used for this segment (for rotation)
    
    # Exclusion tracking (for excluding segments from translation)
    is_excluded: bool = False  # Whether this segment is excluded from translation
    excluded_at: Optional[float] = None  # Exclusion timestamp
    exclusion_reason: Optional[str] = None  # Exclusion reason (ExclusionReason enum value)
    exclusion_metadata: Optional[dict] = None  # Additional exclusion metadata (e.g., detected_lang for LANGUAGE_MATCH)
    
    # Layout mapping (for high-fidelity PDF restoration)
    layout_block_indices: list[int] = field(default_factory=list)  # Indices of layout blocks this segment maps to

    # Optional user font size override for PDF overlay (pt). None = auto.
    font_size_pt: Optional[float] = None
    font_weight: Optional[str] = None
    font_style: Optional[str] = None
    leading_em: Optional[float] = None

    # Optional rotation for overlay placement: 0=none, 90=CW, 180=flip, 270=CCW.
    # Applied when the source bbox dimension does not match the translated text's
    # reading direction (e.g., table rotated 90 in the original PDF).
    rotation: int = 0

    # Optional table grid stroke width for PDF overlay tables (pt). 0 = hidden.
    table_stroke_pt: Optional[float] = None
    # Optional table border style: grid | booktabs | booktabs_2 | booktabs_3 | horizontal | outer | none
    table_border_style: Optional[str] = None
    
    @classmethod
    def create(
        cls,
        task_id: str,
        segment_index: int,
        source_text: str,
        target_text: str,
        source_format: Optional[str] = None,
        workflow_type: Optional[str] = None,
    ) -> "TranslationSegment":
        """Create a new translation segment."""
        segment_id = f"{task_id}_segment_{segment_index}"
        return cls(
            segment_id=segment_id,
            task_id=task_id,
            segment_index=segment_index,
            source_text=source_text,
            target_text=target_text,
            source_length=len(source_text),
            target_length=len(target_text),
            source_format=source_format,
            workflow_type=workflow_type,
        )
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "segment_id": self.segment_id,
            "task_id": self.task_id,
            "segment_index": self.segment_index,
            "source_text": self.source_text,
            "target_text": self.target_text,
            "source_length": self.source_length,
            "target_length": self.target_length,
            "status": self.status,
            "reviewed": self.reviewed,
            "modified": self.modified,
            "modified_text": self.modified_text,
            "modified_by": self.modified_by,
            "modified_at": self.modified_at,
            "review_notes": self.review_notes,
            "created_at": self.created_at,
            "source_format": self.source_format,
            "workflow_type": self.workflow_type,
            "platform_used": self.platform_used,
            "is_failed": self.is_failed,
            "failure_reason": self.failure_reason,
            "needs_retry": self.needs_retry,
            "retry_count": self.retry_count,
            "used_platforms": self.used_platforms,
            "is_excluded": self.is_excluded,
            "excluded_at": self.excluded_at,
            "exclusion_reason": self.exclusion_reason,
            "exclusion_metadata": self.exclusion_metadata,
            "layout_block_indices": self.layout_block_indices,
            "font_size_pt": self.font_size_pt,
            "font_weight": self.font_weight,
            "font_style": self.font_style,
            "leading_em": self.leading_em,
            "rotation": self.rotation,
            "table_stroke_pt": self.table_stroke_pt,
            "table_border_style": self.table_border_style,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "TranslationSegment":
        """Create from dictionary."""
        return cls(
            segment_id=data["segment_id"],
            task_id=data["task_id"],
            segment_index=data["segment_index"],
            source_text=data["source_text"],
            target_text=data["target_text"],
            source_length=data["source_length"],
            target_length=data["target_length"],
            status=data.get("status", "translated"),
            reviewed=data.get("reviewed", False),
            modified=data.get("modified", False),
            modified_text=data.get("modified_text"),
            modified_by=data.get("modified_by"),
            modified_at=data.get("modified_at"),
            review_notes=data.get("review_notes"),
            created_at=data.get("created_at", time.time()),
            source_format=data.get("source_format"),
            workflow_type=data.get("workflow_type"),
            platform_used=data.get("platform_used"),
            is_failed=data.get("is_failed", False),
            failure_reason=data.get("failure_reason"),
            needs_retry=data.get("needs_retry", False),
            retry_count=data.get("retry_count", 0),
            used_platforms=data.get("used_platforms", []),
            is_excluded=data.get("is_excluded", False),
            excluded_at=data.get("excluded_at"),
            exclusion_reason=data.get("exclusion_reason"),
            exclusion_metadata=data.get("exclusion_metadata"),
            layout_block_indices=data.get("layout_block_indices", []),
            font_size_pt=data.get("font_size_pt"),
            font_weight=data.get("font_weight"),
            font_style=data.get("font_style"),
            leading_em=data.get("leading_em"),
            rotation=data.get("rotation", 0),
            table_stroke_pt=data.get("table_stroke_pt"),
            table_border_style=data.get("table_border_style"),
        )
    
    def update_target_text(self, new_text: str, modified_by: Optional[str] = None) -> None:
        """Update target text with modification tracking."""
        self.modified_text = new_text
        self.target_text = new_text
        self.target_length = len(new_text)
        self.modified = True
        self.modified_by = modified_by
        self.modified_at = time.time()
        self.status = "modified"
    
    def mark_reviewed(self, notes: Optional[str] = None) -> None:
        """Mark segment as reviewed."""
        self.reviewed = True
        self.review_notes = notes
        if self.status == "translated":
            self.status = "reviewed"


@dataclass
class TranslationSegmentsMetadata:
    """Metadata for translation segments collection."""
    
    original_format: Optional[str] = None  # Original file format: 'pdf', 'docx', etc.
    original_filename: Optional[str] = None  # Original filename
    workflow_type: Optional[str] = None  # Workflow type used
    source_lang: Optional[str] = None  # Source language
    target_lang: Optional[str] = None  # Target language
    total_segments: int = 0  # Total number of segments
    created_at: float = field(default_factory=time.time)  # Creation timestamp
    segment_info: Optional[list] = None  # Segment-specific metadata (e.g., cell coordinates for XLSX, paragraph info for DOCX)
    # P0: Clear boundary between PDF (layout-driven) and MD/TXT (text-driven). Export/rebuild use this to avoid mixing.
    source_input_type: Optional[str] = None  # "layout" = PDF with layout_document; "text" = MD/TXT or PDF without layout
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        result = {
            "original_format": self.original_format,
            "original_filename": self.original_filename,
            "workflow_type": self.workflow_type,
            "source_lang": self.source_lang,
            "target_lang": self.target_lang,
            "total_segments": self.total_segments,
            "created_at": self.created_at,
        }
        if self.segment_info is not None:
            result["segment_info"] = self.segment_info
        if self.source_input_type is not None:
            result["source_input_type"] = self.source_input_type
        return result
    
    @classmethod
    def from_dict(cls, data: dict) -> "TranslationSegmentsMetadata":
        """Create from dictionary."""
        return cls(
            original_format=data.get("original_format"),
            original_filename=data.get("original_filename"),
            workflow_type=data.get("workflow_type"),
            source_lang=data.get("source_lang"),
            target_lang=data.get("target_lang"),
            total_segments=data.get("total_segments", 0),
            created_at=data.get("created_at", time.time()),
            segment_info=data.get("segment_info"),
            source_input_type=data.get("source_input_type"),
        )

