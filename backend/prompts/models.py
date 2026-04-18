# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

import uuid
from datetime import datetime
from typing import Optional, List
from dataclasses import dataclass


@dataclass
class PromptItem:
    """Prompt item"""
    name: str  # Prompt name
    content: str  # Prompt content


@dataclass
class PromptFile:
    """Prompt file"""
    id: str  # Unique identifier
    name: str  # Prompt set name
    file_path: str  # File path
    owner: str  # Owner
    is_global: bool = False  # Whether it's a global prompt set
    created_at: datetime = None  # Creation time
    updated_at: datetime = None  # Update time
    item_count: int = 0  # Prompt count
    description: Optional[str] = None  # Description


@dataclass
class UserPromptSelection:
    """User prompt selection"""
    username: str  # Username
    selected_global_prompts: List[str]  # Selected global prompt set ID list
    personal_prompt: Optional[str] = None  # Personal prompt set ID


@dataclass
class PromptVersion:
    """Prompt version information"""
    prompt_id: str
    version: int
    updated_by: str
    updated_at: datetime


def generate_prompt_id() -> str:
    """Generate prompt ID"""
    return str(uuid.uuid4())


def create_prompt_file(
    name: str,
    file_path: str,
    owner: str,
    is_global: bool = False,
    description: Optional[str] = None
) -> PromptFile:
    """Create prompt file object"""
    now = datetime.now()
    return PromptFile(
        id=generate_prompt_id(),
        name=name,
        file_path=file_path,
        owner=owner,
        is_global=is_global,
        created_at=now,
        updated_at=now,
        item_count=0,
        description=description
    )
