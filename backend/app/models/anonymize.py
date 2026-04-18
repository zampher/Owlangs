# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Anonymization-related Pydantic models for Owlangs.

This module contains models for anonymization settings, model management,
and per-language configuration.
"""

from typing import Optional
from pydantic import BaseModel


class _AnonSavePayload(BaseModel):
    """Payload for saving anonymization settings."""
    model_name: str
    models_dir: str | None = None


class _AnonTestPayload(BaseModel):
    """Payload for testing anonymization models."""
    model_name: str
    models_dir: str | None = None
    text: str | None = None


class _PerLangModel(BaseModel):
    """Model for per-language anonymization configuration."""
    preferred: str
    models_dir: str | None = None
    fallback: bool = True


class _PerLangSavePayload(BaseModel):
    """Payload for saving per-language model configuration."""
    language: str
    preferred: str
    models_dir: str | None = None
    fallback: bool = True


class _AnonDownloadPayload(BaseModel):
    """Payload for downloading anonymization models."""
    language: str
    model_name: str
    models_dir: str | None = None
