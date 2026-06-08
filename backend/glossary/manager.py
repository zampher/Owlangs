# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

from backend.logger import unified_logger as logger
from logger.logger import LogModule
from typing import Dict, List, Optional, Tuple
from datetime import datetime

from .models import GlossaryFile, GlossaryItem, UserGlossarySelection
from .storage import get_glossary_storage

class GlossaryManager:
    """Glossary manager"""
    
    def __init__(self):
        self.storage = get_glossary_storage()
    
    def get_global_glossaries(self) -> List[GlossaryFile]:
        """Get global glossary list"""
        return self.storage.get_global_glossaries()
    
    def get_user_personal_glossary(self, username: str) -> Optional[GlossaryFile]:
        """Get user personal glossary"""
        return self.storage.get_user_personal_glossary(username)
    
    def get_user_selection(self, username: str) -> UserGlossarySelection:
        """Get user glossary selection"""
        return self.storage.get_user_selection(username)
    
    def save_user_selection(self, selection: UserGlossarySelection):
        """Save user glossary selection"""
        self.storage.save_user_selection(selection)
    
    def create_global_glossary(
        self, 
        name: str, 
        glossary_dict: Dict[str, str], 
        owner: str,
        description: Optional[str] = None
    ) -> GlossaryFile:
        """Create global glossary"""
        return self.storage.create_global_glossary(name, glossary_dict, owner, description)
    
    def update_global_glossary(
        self, 
        glossary_id: str, 
        glossary_dict: Dict[str, str], 
        updated_by: str
    ) -> bool:
        """Update global glossary"""
        return self.storage.update_global_glossary(glossary_id, glossary_dict, updated_by)
    
    def delete_global_glossary(self, glossary_id: str) -> bool:
        """Delete global glossary"""
        return self.storage.delete_global_glossary(glossary_id)
    
    def save_user_personal_glossary(
        self, 
        username: str, 
        glossary_dict: Dict[str, str]
    ) -> bool:
        """Save user personal glossary"""
        return self.storage.save_user_personal_glossary(username, glossary_dict)
    
    def save_glossary_with_categories(
        self, 
        glossary_id: str, 
        glossary_dict: Dict[str, Dict[str, str]], 
        updated_by: str
    ) -> bool:
        """Save glossary with categories"""
        try:
            if glossary_id.startswith('global_'):
                # For global glossaries, we need to update the CSV file directly
                global_glossaries = self.get_global_glossaries()
                for glossary in global_glossaries:
                    if glossary.id == glossary_id:
                        self.storage.save_glossary_with_categories_to_csv(glossary_dict, glossary.file_path)
                        self.update_glossary_version(glossary_id, updated_by)
                        return True
                return False
            elif glossary_id.startswith('personal_'):
                # For personal glossaries, convert to old format for compatibility
                old_format = {src: entry['dst'] for src, entry in glossary_dict.items()}
                return self.storage.save_user_personal_glossary(glossary_id.replace('personal_', ''), old_format)
            return False
        except Exception as e:
            logger.error(LogModule.GLOSSARY, f"Failed to save glossary with categories {glossary_id}: {e}")
            return False
    
    def save_glossary_with_languages(
        self,
        glossary_id: str,
        glossary_dict: Dict[str, Dict[str, str]],
        updated_by: str,
    ) -> bool:
        """Save glossary with languages (src -> {dst, category, target_lang})."""
        try:
            if glossary_id.startswith('global_'):
                global_glossaries = self.get_global_glossaries()
                for glossary in global_glossaries:
                    if glossary.id == glossary_id:
                        self.storage.save_glossary_with_languages_to_csv(glossary_dict, glossary.file_path)
                        self.update_glossary_version(glossary_id, updated_by)
                        return True
                return False
            elif glossary_id.startswith('personal_'):
                # For personal, degrade to old format for now (ignore language fields)
                old_format = {src: entry.get('dst', '') for src, entry in glossary_dict.items()}
                return self.storage.save_user_personal_glossary(glossary_id.replace('personal_', ''), old_format)
            return False
        except Exception as e:
            logger.error(LogModule.GLOSSARY, f"Failed to save glossary with languages {glossary_id}: {e}")
            return False

    def get_glossary_content(self, glossary_id: str) -> Optional[Dict[str, str]]:
        """Get glossary content (backward compatible)"""
        try:
            # Check if it's a global glossary
            if glossary_id.startswith('global_'):
                global_glossaries = self.get_global_glossaries()
                for glossary in global_glossaries:
                    if glossary.id == glossary_id:
                        return self.storage.load_glossary_from_csv(glossary.file_path)
            
            # Check if it's a personal glossary
            elif glossary_id.startswith('personal_'):
                username = glossary_id.replace('personal_', '')
                personal_glossary = self.get_user_personal_glossary(username)
                if personal_glossary:
                    return self.storage.load_glossary_from_csv(personal_glossary.file_path)
            
            return None
        except Exception as e:
            logger.error(LogModule.GLOSSARY, f"Failed to get glossary content {glossary_id}: {e}")
            return None
    
    def get_glossary_content_with_categories(self, glossary_id: str) -> Optional[Dict[str, Dict[str, str]]]:
        """Get glossary content with categories"""
        try:
            # Check if it's a global glossary
            if glossary_id.startswith('global_'):
                global_glossaries = self.get_global_glossaries()
                for glossary in global_glossaries:
                    if glossary.id == glossary_id:
                        return self.storage.load_glossary_with_categories_from_csv(glossary.file_path)
            
            # Check if it's a personal glossary
            elif glossary_id.startswith('personal_'):
                username = glossary_id.replace('personal_', '')
                personal_glossary = self.get_user_personal_glossary(username)
                if personal_glossary:
                    return self.storage.load_glossary_with_categories_from_csv(personal_glossary.file_path)
            
            return None
        except Exception as e:
            logger.error(LogModule.GLOSSARY, f"Failed to get glossary content with categories {glossary_id}: {e}")
            return None

    def get_glossary_content_with_languages(self, glossary_id: str) -> Optional[Dict[str, Dict[str, str]]]:
        """Get glossary content with languages (src -> {dst, category, target_lang}).
        
        Note: source_lang is removed, only target_lang is kept.
        """
        try:
            if glossary_id.startswith('global_'):
                global_glossaries = self.get_global_glossaries()
                for glossary in global_glossaries:
                    if glossary.id == glossary_id:
                        return self.storage.load_glossary_with_languages_from_csv(glossary.file_path)
            elif glossary_id.startswith('personal_'):
                username = glossary_id.replace('personal_', '')
                personal_glossary = self.get_user_personal_glossary(username)
                if personal_glossary:
                    return self.storage.load_glossary_with_languages_from_csv(personal_glossary.file_path)
            return None
        except Exception as e:
            logger.error(LogModule.GLOSSARY, f"Failed to get glossary content with languages {glossary_id}: {e}")
            return None
    
    def merge_user_glossaries(self, username: str) -> Dict[str, str]:
        """Merge user selected glossaries"""
        selection = self.get_user_selection(username)
        merged_glossary = {}
        
        # 1. Add selected global glossaries (lower priority)
        for global_id in selection.selected_global_glossaries:
            global_content = self.get_glossary_content(global_id)
            if global_content:
                merged_glossary.update(global_content)
        
        # 2. Add personal glossary (higher priority, will override conflicts)
        if selection.personal_glossary:
            personal_content = self.get_glossary_content(selection.personal_glossary)
            if personal_content:
                merged_glossary.update(personal_content)
        
        return merged_glossary
    
    def get_all_versions(self) -> Dict[str, float]:
        """Get all glossary versions"""
        return self.storage.get_all_versions()
    
    def get_glossary_version(self, glossary_id: str) -> float:
        """Get glossary version"""
        return self.storage.get_glossary_version(glossary_id)
    
    def update_glossary_version(self, glossary_id: str, updated_by: str):
        """Update glossary version"""
        self.storage.update_glossary_version(glossary_id, updated_by)
    
    def validate_glossary_dict(self, glossary_dict: Dict[str, str]) -> Tuple[bool, str]:
        """Validate glossary dictionary"""
        if not isinstance(glossary_dict, dict):
            return False, "Glossary must be in dictionary format"
        
        if len(glossary_dict) == 0:
            return False, "Glossary cannot be empty"
        
        for src, dst in glossary_dict.items():
            if not isinstance(src, str) or not isinstance(dst, str):
                return False, "Glossary keys and values must be strings"
            
            if not src.strip() or not dst.strip():
                return False, "Glossary keys and values cannot be empty"
        
        return True, "Validation passed"
    
    def get_glossary_statistics(self) -> Dict[str, int]:
        """Get glossary statistics"""
        global_glossaries = self.get_global_glossaries()
        total_global_items = sum(glossary.item_count for glossary in global_glossaries)
        
        return {
            "global_glossaries_count": len(global_glossaries),
            "total_global_items": total_global_items,
            "average_items_per_glossary": total_global_items // len(global_glossaries) if global_glossaries else 0
        }


# Global manager instance
_glossary_manager = None


def get_glossary_manager() -> GlossaryManager:
    """Get glossary manager instance"""
    global _glossary_manager
    if _glossary_manager is None:
        _glossary_manager = GlossaryManager()
    return _glossary_manager
