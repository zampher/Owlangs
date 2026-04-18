# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Exclusion reason enumeration for translation segments.
"""

from enum import Enum


class ExclusionReason(str, Enum):
    """
    Exclusion reason types for translation segments.
    
    Categories:
    - Content-based: Should always be excluded regardless of target language
    - Language-based: May change with target language
    - User-based: User manually selected
    """
    
    # Content-based exclusions (should always be excluded)
    IMAGE = "image"                    # Image placeholder or image content
    FORMULA = "formula"                # LaTeX/MathML formula
    REFERENCE = "reference"            # Reference/citation text
    IDENTIFIER = "identifier"          # URL, email, serial number, code, etc.
    STRUCTURAL = "structural"          # Header, footer, footnote, etc.
    
    # Optional exclusions (can be excluded by user choice, default: not excluded)
    TABLE = "table"                    # Table content (markdown table, PDF table block, etc.)
                                        # Default: not excluded (most tables can be translated)
                                        # User can choose to exclude tables if needed
    
    # Language-based exclusions (may change with target language)
    LANGUAGE_MATCH = "language_match"  # Source language matches target language
    
    # User-based exclusions
    USER_SELECTED = "user_selected"    # User manually selected to exclude
    
    # Legacy/unknown (for backward compatibility)
    UNKNOWN = "unknown"                # Unknown reason (legacy data)
    
    @classmethod
    def is_content_based(cls, reason: "ExclusionReason") -> bool:
        """Check if exclusion reason is content-based (should always be excluded)."""
        return reason in {
            cls.IMAGE,
            cls.FORMULA,
            cls.REFERENCE,
            cls.IDENTIFIER,
            cls.STRUCTURAL,
        }
        # Note: TABLE is NOT content-based - it's optional (user can choose to exclude)
    
    @classmethod
    def is_optional(cls, reason: "ExclusionReason") -> bool:
        """Check if exclusion reason is optional (can be excluded by user choice, default: not excluded)."""
        return reason == cls.TABLE

    @classmethod
    def is_default_not_excluded(cls, reason: "ExclusionReason") -> bool:
        """Reasons that are detected but not excluded by default; user chooses via checkbox (Structural, Language Match, Table)."""
        return reason in {cls.TABLE, cls.STRUCTURAL, cls.LANGUAGE_MATCH}

    @classmethod
    def is_language_based(cls, reason: "ExclusionReason") -> bool:
        """Check if exclusion reason is language-based (may change with target language)."""
        return reason == cls.LANGUAGE_MATCH
    
    @classmethod
    def is_user_based(cls, reason: "ExclusionReason") -> bool:
        """Check if exclusion reason is user-based."""
        return reason == cls.USER_SELECTED

    @classmethod
    def get_default_excluded(cls) -> set:
        """Return the set of ExclusionReasons that should be auto-excluded
        based on the ``exclusion_defaults`` section in system.json.

        Falls back to the original hard-coded defaults when the config
        cannot be loaded (e.g. during unit tests).
        """
        try:
            from config.system_config import get_system_config
            cfg = get_system_config().exclusion_defaults
            _mapping = {
                cls.IMAGE: cfg.image,
                cls.FORMULA: cfg.formula,
                cls.REFERENCE: cfg.reference,
                cls.IDENTIFIER: cfg.identifier,
                cls.STRUCTURAL: cfg.structural,
                cls.TABLE: cfg.table,
                cls.LANGUAGE_MATCH: cfg.language_match,
            }
            return {reason for reason, enabled in _mapping.items() if enabled}
        except Exception:
            # Fallback: original hard-coded defaults
            return {cls.IMAGE, cls.FORMULA, cls.REFERENCE, cls.IDENTIFIER}
