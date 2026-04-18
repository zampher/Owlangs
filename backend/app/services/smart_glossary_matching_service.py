# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Smart Glossary Matching Service for Owlangs.

This service implements intelligent glossary matching with priority-based merging:
1. Exact match (src, category, language_pair) - highest priority
2. Reverse match (dst, category, language_pair) - medium priority  
3. General match (src, any category, any language) - lowest priority

The service also supports language filtering and category-based matching.
"""

from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass

from logger import unified_logger as logger
from logger.logger import LogModule


@dataclass
class GlossaryEntry:
    """Glossary entry with metadata for smart matching."""
    src: str
    dst: str
    category: str = ""
    target_lang: str = ""
    priority: int = 0  # 0=exact, 1=reverse, 2=general


class SmartGlossaryMatchingService:
    """Service for intelligent glossary matching with priority-based merging."""
    
    def __init__(self):
        self.logger = logger
    
    def merge_glossaries_with_smart_matching(
        self,
        user_glossaries: Dict[str, Dict[str, str]],
        target_language: str = "",
        categories: Optional[List[str]] = None,
        enable_smart_matching: bool = True
    ) -> Dict[str, str]:
        """
        Merge user glossaries with smart matching and priority-based merging.
        
        Args:
            user_glossaries: Dictionary of glossary_id -> {src: {dst, category, target_lang}}
            target_language: Target language filter (empty = any)
            categories: List of categories to include (None = any)
            enable_smart_matching: Whether to enable smart matching (exact > reverse > general)
            
        Returns:
            Merged glossary dictionary {src: dst} with priority-based merging
        """
        if not enable_smart_matching:
            # Fallback to simple merging (original behavior)
            return self._simple_merge_glossaries(user_glossaries, target_language, categories)
        
        self.logger.info(LogModule.GLOSSARY,f"Starting smart glossary matching for {len(user_glossaries)} glossaries")
        
        # Collect all entries with metadata
        all_entries = []
        for glossary_id, glossary_content in user_glossaries.items():
            # Determine glossary priority: personal > global
            is_personal = glossary_id.startswith('personal_')
            base_priority = 0 if is_personal else 10  # Personal gets higher priority (lower number)
            
            for src, entry_data in glossary_content.items():
                if isinstance(entry_data, dict):
                    entry = GlossaryEntry(
                        src=src,
                        dst=entry_data.get('dst', ''),
                        category=entry_data.get('category', ''),
                        target_lang=entry_data.get('target_lang', ''),
                        priority=base_priority  # Will be adjusted during matching
                    )
                    all_entries.append(entry)
        
        # Apply language filtering (only target_language is used now)
        if target_language:
            filtered_entries = []
            for entry in all_entries:
                if self._matches_language_filter(entry, target_language):
                    filtered_entries.append(entry)
            all_entries = filtered_entries
        
        # Apply category filtering
        if categories:
            filtered_entries = []
            for entry in all_entries:
                if self._matches_category_filter(entry, categories):
                    filtered_entries.append(entry)
            all_entries = filtered_entries
        
        self.logger.info(LogModule.GLOSSARY,f"After filtering: {len(all_entries)} entries")
        
        # Group entries by source text for smart matching
        grouped_entries = self._group_entries_by_source(all_entries)
        
        # Apply smart matching with priority
        merged_glossary = {}
        for src, entries in grouped_entries.items():
            best_entry = self._select_best_entry(entries, target_language)
            if best_entry:
                merged_glossary[src] = best_entry.dst
                self.logger.debug(LogModule.GLOSSARY, f"Selected {best_entry.src} -> {best_entry.dst} (priority: {best_entry.priority})")
        
        self.logger.info(LogModule.GLOSSARY,f"Smart matching completed: {len(merged_glossary)} final entries")
        return merged_glossary
    
    def _simple_merge_glossaries(
        self,
        user_glossaries: Dict[str, Dict[str, str]],
        target_language: str = "",
        categories: Optional[List[str]] = None
    ) -> Dict[str, str]:
        """Simple merging without smart matching (original behavior)."""
        merged_glossary = {}
        
        for glossary_id, glossary_content in user_glossaries.items():
            for src, entry_data in glossary_content.items():
                if isinstance(entry_data, dict):
                    dst = entry_data.get('dst', '')
                    category = entry_data.get('category', '')
                    target_lang = entry_data.get('target_lang', '')
                    
                    # Apply language filtering (only target_language is used now)
                    if target_language and not self._matches_language_filter(
                        GlossaryEntry(src=src, dst=dst, category=category, target_lang=target_lang),
                        target_language
                    ):
                        continue
                    
                    # Apply category filtering
                    if categories and not self._matches_category_filter(
                        GlossaryEntry(src=src, dst=dst, category=category, target_lang=target_lang),
                        categories
                    ):
                        continue
                    
                    # Simple merge (last wins)
                    merged_glossary[src] = dst
        
        return merged_glossary
    
    def _matches_language_filter(self, entry: GlossaryEntry, target_lang: str) -> bool:
        """Check if entry matches language filter (only target_lang is used)."""
        if not target_lang:
            return True
        
        if entry.target_lang and entry.target_lang != target_lang:
            return False
        
        return True
    
    def _matches_category_filter(self, entry: GlossaryEntry, categories: List[str]) -> bool:
        """Check if entry matches category filter."""
        if not categories:
            return True
        
        # Empty category matches if "未分类" is in categories
        if not entry.category:
            return "未分类" in categories or "uncategorized" in categories
        
        return entry.category in categories
    
    def _group_entries_by_source(self, entries: List[GlossaryEntry]) -> Dict[str, List[GlossaryEntry]]:
        """Group entries by source text."""
        grouped = {}
        for entry in entries:
            if entry.src not in grouped:
                grouped[entry.src] = []
            grouped[entry.src].append(entry)
        return grouped
    
    def _select_best_entry(
        self,
        entries: List[GlossaryEntry],
        target_language: str = ""
    ) -> Optional[GlossaryEntry]:
        """
        Select the best entry based on priority: exact > reverse > general.
        
        Priority rules:
        1. Exact match: (src, category, target_lang) - priority 0
        2. Reverse match: (dst, category, target_lang) - priority 1  
        3. General match: (src, any category, any target_lang) - priority 2
        """
        if not entries:
            return None
        
        # Calculate priority for each entry
        for entry in entries:
            entry.priority = self._calculate_priority(entry, target_language)
        
        # Sort by priority (lower number = higher priority)
        entries.sort(key=lambda x: x.priority)
        
        # Return the highest priority entry
        best_entry = entries[0]
        self.logger.debug(LogModule.GLOSSARY, f"Selected entry {best_entry.src} -> {best_entry.dst} with priority {best_entry.priority}")
        
        return best_entry
    
    def _calculate_priority(self, entry: GlossaryEntry, target_lang: str) -> int:
        """Calculate priority for an entry (lower number = higher priority)."""
        # Start with base priority (personal=0, global=10)
        base_priority = entry.priority
        
        # Language matching bonus (only target_lang is used)
        language_bonus = 0
        if entry.target_lang == target_lang and target_lang:
            language_bonus = 0  # Perfect match
        elif target_lang:
            language_bonus = 1  # No match or empty target_lang
        else:
            language_bonus = 0  # No target_lang filter, no bonus
        
        # Final priority = base_priority + language_bonus
        return base_priority + language_bonus


# Service instance
smart_glossary_matching_service = SmartGlossaryMatchingService()

