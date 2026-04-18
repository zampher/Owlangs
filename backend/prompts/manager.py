# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime

from .models import PromptFile, PromptItem, UserPromptSelection
from .storage import get_prompt_storage

logger = logging.getLogger(__name__)


class PromptManager:
    """Prompt manager"""
    
    def __init__(self):
        self.storage = get_prompt_storage()
    
    def get_global_prompts(self) -> List[PromptFile]:
        """Get global prompt list"""
        return self.storage.get_global_prompts()
    
    def get_user_personal_prompt(self, username: str) -> Optional[PromptFile]:
        """Get user personal prompt"""
        return self.storage.get_user_personal_prompt(username)
    
    def get_user_selection(self, username: str) -> UserPromptSelection:
        """Get user prompt selection"""
        return self.storage.get_user_selection(username)
    
    def save_user_selection(self, selection: UserPromptSelection):
        """Save user prompt selection"""
        self.storage.save_user_selection(selection)
    
    def create_global_prompt(
        self, 
        name: str, 
        prompts_dict: Dict[str, str], 
        owner: str,
        description: Optional[str] = None
    ) -> PromptFile:
        """Create global prompt"""
        return self.storage.create_global_prompt(name, prompts_dict, owner, description)
    
    def update_global_prompt(
        self, 
        prompt_id: str, 
        prompts_dict: Dict[str, str], 
        updated_by: str
    ) -> bool:
        """Update global prompt"""
        return self.storage.update_global_prompt(prompt_id, prompts_dict, updated_by)
    
    def delete_global_prompt(self, prompt_id: str) -> bool:
        """Delete global prompt"""
        return self.storage.delete_global_prompt(prompt_id)
    
    def save_user_personal_prompt(
        self, 
        username: str, 
        prompts_dict: Dict[str, str]
    ) -> bool:
        """Save user personal prompt"""
        return self.storage.save_user_personal_prompt(username, prompts_dict)
    
    def get_all_versions(self) -> Dict[str, List[dict]]:
        """Get all version information"""
        return self.storage.get_all_versions()
    
    def get_prompt_versions(self, prompt_id: str) -> List:
        """Get prompt version list"""
        return self.storage.get_prompt_versions(prompt_id)
    
    def validate_prompt_dict(self, prompts_dict: Dict[str, str]) -> Tuple[bool, str]:
        """Validate prompt dictionary"""
        if not prompts_dict:
            return False, "Prompts cannot be empty"
        
        # Check for duplicate prompt names
        names = list(prompts_dict.keys())
        if len(names) != len(set(names)):
            return False, "Prompt names cannot be duplicated"
        
        # Check prompt names and content
        for name, content in prompts_dict.items():
            if not name or not name.strip():
                return False, "Prompt name cannot be empty"
            if not content or not content.strip():
                return False, f"Prompt '{name}' content cannot be empty"
            
            # Check name length
            if len(name.strip()) > 100:
                return False, f"Prompt name '{name}' is too long (max 100 characters)"
            
            # Check content length
            if len(content.strip()) > 10000:
                return False, f"Prompt '{name}' content is too long (max 10000 characters)"
        
        return True, "Validation passed"
    
    def get_merged_prompts(self, username: str) -> Dict[str, str]:
        """Get user merged prompts (including selected global prompts and personal prompts)"""
        user_selection = self.get_user_selection(username)
        merged_prompts = {}
        
        # Add selected global prompts
        for prompt_id in user_selection.selected_global_prompts:
            global_prompts = self.get_global_prompts()
            for prompt_file in global_prompts:
                if prompt_file.id == prompt_id:
                    prompts_dict = self.storage.load_prompts_from_json(
                        self.storage.global_dir / self.storage.global_prompts[prompt_id]['file_path']
                    )
                    # Add prefix to avoid conflicts
                    for name, content in prompts_dict.items():
                        prefixed_name = f"[{prompt_file.name}] {name}"
                        merged_prompts[prefixed_name] = content
                    break
        
        # Add personal prompts (higher priority, will override global prompts with same name)
        if user_selection.personal_prompt:
            personal_prompt = self.get_user_personal_prompt(username)
            if personal_prompt:
                prompts_dict = self.storage.load_prompts_from_json(
                    self.storage.users_dir / f"{username}_prompts.json"
                )
                merged_prompts.update(prompts_dict)
        
        return merged_prompts
    
    def get_prompt_statistics(self) -> Dict[str, int]:
        """Get prompt statistics"""
        global_prompts = self.get_global_prompts()
        total_global_items = sum(p.item_count for p in global_prompts)
        
        return {
            "global_prompt_count": len(global_prompts),
            "total_global_items": total_global_items,
            "total_users": len(self.storage.user_selections)
        }


# Global manager instance
_prompt_manager = None


def get_prompt_manager() -> PromptManager:
    """Get prompt manager instance"""
    global _prompt_manager
    if _prompt_manager is None:
        _prompt_manager = PromptManager()
    return _prompt_manager
