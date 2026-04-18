# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

from dataclasses import dataclass
from typing import Dict, List, Optional
from datetime import datetime
import uuid


@dataclass
class GlossaryItem:
    """Glossary item"""
    src: str  # Source text
    dst: str  # Target text


@dataclass
class GlossaryFile:
    """Glossary file"""
    id: str  # Unique identifier
    name: str  # Display name
    file_path: str  # File path
    owner: str  # Owner (username)
    is_global: bool  # Whether it's a global glossary
    created_at: datetime
    updated_at: datetime
    item_count: int  # Term count
    description: Optional[str] = None  # Description


@dataclass
class UserGlossarySelection:
    """User glossary selection"""
    username: str
    selected_global_glossaries: List[str]  # Selected global glossary ID list
    personal_glossary: Optional[str] = None  # Personal glossary ID


@dataclass
class GlossaryVersion:
    """Glossary version information"""
    glossary_id: str
    version: float  # Timestamp
    updated_by: str  # Updated by
    updated_at: datetime


def generate_glossary_id() -> str:
    """Generate glossary ID"""
    return str(uuid.uuid4())


def create_glossary_file(
    name: str,
    file_path: str,
    owner: str,
    is_global: bool = False,
    description: Optional[str] = None
) -> GlossaryFile:
    """Create glossary file object"""
    now = datetime.now()
    return GlossaryFile(
        id=generate_glossary_id(),
        name=name,
        file_path=file_path,
        owner=owner,
        is_global=is_global,
        created_at=now,
        updated_at=now,
        item_count=0,
        description=description
    )
