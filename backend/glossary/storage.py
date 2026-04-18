# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

import json
import csv
import time
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime

from logger import unified_logger as logger
from logger.logger import LogModule

from .models import GlossaryFile, GlossaryItem, UserGlossarySelection, GlossaryVersion


class GlossaryStorage:
    """Glossary storage manager"""
    
    def __init__(self, base_dir: str = None):
        if base_dir is None:
            from utils.path_utils import get_owlangs_paths
            paths = get_owlangs_paths()
            base_dir = paths["glossaries"]
        self.base_dir = Path(base_dir)
        self.global_dir = self.base_dir / "global"
        self.users_dir = self.base_dir / "users"
        self.metadata_dir = self.base_dir / "metadata"
        
        # Metadata files
        self.global_glossaries_file = self.metadata_dir / "global_glossaries.json"
        self.user_selections_file = self.metadata_dir / "user_selections.json"
        self.versions_file = self.metadata_dir / "versions.json"
        
        # Create directory structure
        self._ensure_directories()
        
        # Load metadata
        self.global_glossaries = self._load_global_glossaries()
        self.user_selections = self._load_user_selections()
        self.versions = self._load_versions()
        # Perform metadata self-check on startup, clean up invalid items
        try:
            self.reconcile_metadata()
        except Exception as _e:
            logger.warning(LogModule.GLOSSARY, f"Glossary metadata self-check failed on startup: {_e}")
    
    def _ensure_directories(self):
        """Ensure directory structure exists"""
        self.global_dir.mkdir(parents=True, exist_ok=True)
        self.users_dir.mkdir(parents=True, exist_ok=True)
        self.metadata_dir.mkdir(parents=True, exist_ok=True)
    
    def _load_global_glossaries(self) -> Dict[str, dict]:
        """Load global glossary metadata"""
        if self.global_glossaries_file.exists():
            try:
                with open(self.global_glossaries_file, 'r', encoding='utf-8-sig') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(LogModule.GLOSSARY, f"Failed to load global glossary metadata: {e}")
        return {}
    
    def _save_global_glossaries(self):
        """Save global glossary metadata"""
        try:
            with open(self.global_glossaries_file, 'w', encoding='utf-8') as f:
                json.dump(self.global_glossaries, f, indent=2, ensure_ascii=False, default=str)
        except Exception as e:
            logger.error(LogModule.GLOSSARY, f"Failed to save global glossary metadata: {e}")
    
    def _load_user_selections(self) -> Dict[str, dict]:
        """Load user selection metadata"""
        if self.user_selections_file.exists():
            try:
                with open(self.user_selections_file, 'r', encoding='utf-8-sig') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(LogModule.GLOSSARY, f"Failed to load user selection metadata: {e}")
        return {}
    
    def _save_user_selections(self):
        """Save user selection metadata"""
        try:
            with open(self.user_selections_file, 'w', encoding='utf-8') as f:
                json.dump(self.user_selections, f, indent=2, ensure_ascii=False, default=str)
        except Exception as e:
            logger.error(LogModule.GLOSSARY, f"Failed to save user selection metadata: {e}")
    
    def _load_versions(self) -> Dict[str, float]:
        """Load version information"""
        if self.versions_file.exists():
            try:
                with open(self.versions_file, 'r', encoding='utf-8-sig') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(LogModule.GLOSSARY, f"Failed to load version information: {e}")
        return {}
    
    def _save_versions(self):
        """Save version information"""
        try:
            with open(self.versions_file, 'w', encoding='utf-8') as f:
                json.dump(self.versions, f, indent=2)
        except Exception as e:
            logger.error(LogModule.GLOSSARY, f"Failed to save version information: {e}")
    
    def update_glossary_version(self, glossary_id: str, updated_by: str):
        """Update glossary version"""
        self.versions[glossary_id] = time.time()
        self._save_versions()
        logger.info(LogModule.GLOSSARY, f"Glossary {glossary_id} version updated, updated by: {updated_by}")
    
    def get_glossary_version(self, glossary_id: str) -> float:
        """Get glossary version"""
        return self.versions.get(glossary_id, 0)
    
    def get_all_versions(self) -> Dict[str, float]:
        """Get all glossary versions"""
        return self.versions.copy()
    
    def load_glossary_from_csv(self, file_path: Path) -> Dict[str, str]:
        """Load glossary from CSV file (backward compatible)"""
        logger.debug(LogModule.GLOSSARY, f"Loading glossary from CSV file: {file_path}")
        glossary_dict = {}
        try:
            with open(file_path, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    src = row.get('src', '').strip()
                    dst = row.get('dst', '').strip()
                    if src and dst:
                        glossary_dict[src] = dst
        except Exception as e:
            logger.error(LogModule.GLOSSARY, f"Failed to load CSV file {file_path}: {e}")
            raise
        return glossary_dict
    
    def load_glossary_with_categories_from_csv(self, file_path: Path) -> Dict[str, Dict[str, str]]:
        """Load glossary from CSV file with categories (src -> {dst, category})"""
        logger.debug(LogModule.GLOSSARY, f"Loading glossary with categories from CSV file: {file_path}")
        glossary_dict = {}
        try:
            with open(file_path, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    src = row.get('src', '').strip()
                    dst = row.get('dst', '').strip()
                    category = row.get('category', '').strip()  # 保留空白，不填充默认值
                    if src and dst:
                        glossary_dict[src] = {
                            'dst': dst,
                            'category': category
                        }
        except Exception as e:
            logger.error(LogModule.GLOSSARY, f"Failed to load CSV file with categories {file_path}: {e}")
            raise
        return glossary_dict
    
    def load_glossary_with_languages_from_csv(self, file_path: Path) -> Dict[str, Dict[str, str]]:
        """Load glossary from CSV file with languages (src -> {dst, category, target_lang})
        
        Note: source_lang is removed, only target_lang is kept.
        """
        logger.debug(LogModule.GLOSSARY, f"Loading glossary with languages from CSV file: {file_path}")
        glossary_dict = {}
        try:
            with open(file_path, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    src = row.get('src', '').strip()
                    dst = row.get('dst', '').strip()
                    category = row.get('category', '').strip()
                    target_lang = row.get('target_lang', '').strip()
                    if src and dst:
                        glossary_dict[src] = {
                            'dst': dst,
                            'category': category,
                            'target_lang': target_lang
                        }
        except Exception as e:
            logger.error(LogModule.GLOSSARY, f"Failed to load CSV file with languages {file_path}: {e}")
            raise
        return glossary_dict
    
    def save_glossary_to_csv(self, glossary_dict: Dict[str, str], file_path: Path):
        """Save glossary to CSV file (backward compatible)"""
        try:
            with open(file_path, 'w', encoding='utf-8-sig', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['src', 'dst'])
                for src, dst in glossary_dict.items():
                    writer.writerow([src, dst])
        except Exception as e:
            logger.error(LogModule.GLOSSARY, f"Failed to save CSV file {file_path}: {e}")
            raise
    
    def save_glossary_with_categories_to_csv(self, glossary_dict: Dict[str, Dict[str, str]], file_path: Path):
        """Save glossary to CSV file with categories (src -> {dst, category})"""
        try:
            with open(file_path, 'w', encoding='utf-8-sig', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['src', 'dst', 'category'])
                for src, entry in glossary_dict.items():
                    dst = entry.get('dst', '')
                    category = entry.get('category', '')  # 保留空白
                    writer.writerow([src, dst, category])
        except Exception as e:
            logger.error(LogModule.GLOSSARY, f"Failed to save CSV file with categories {file_path}: {e}")
            raise
    
    def save_glossary_with_languages_to_csv(self, glossary_dict: Dict[str, Dict[str, str]], file_path: Path):
        """Save glossary to CSV file with languages (src -> {dst, category, target_lang})"""
        try:
            with open(file_path, 'w', encoding='utf-8-sig', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['src', 'dst', 'category', 'target_lang'])
                for src, entry in glossary_dict.items():
                    dst = entry.get('dst', '')
                    category = entry.get('category', '')
                    target_lang = entry.get('target_lang', '')
                    writer.writerow([src, dst, category, target_lang])
        except Exception as e:
            logger.error(LogModule.GLOSSARY, f"Failed to save CSV file with languages {file_path}: {e}")
            raise
    
    def get_global_glossaries(self) -> List[GlossaryFile]:
        """Get global glossary list"""
        glossaries = []
        for glossary_id, metadata in self.global_glossaries.items():
            file_path = self.global_dir / metadata['file_path']
            if file_path.exists():
                # Calculate term count
                try:
                    glossary_dict = self.load_glossary_from_csv(file_path)
                    item_count = len(glossary_dict)
                except:
                    item_count = 0
                
                glossary = GlossaryFile(
                    id=glossary_id,
                    name=metadata['name'],
                    file_path=str(file_path),
                    owner=metadata['owner'],
                    is_global=True,
                    created_at=datetime.fromisoformat(metadata['created_at']),
                    updated_at=datetime.fromisoformat(metadata['updated_at']),
                    item_count=item_count,
                    description=metadata.get('description')
                )
                glossaries.append(glossary)
        return glossaries
    
    def get_user_personal_glossary(self, username: str) -> Optional[GlossaryFile]:
        """Get user personal glossary"""
        user_dir = self.users_dir / username
        personal_file = user_dir / "personal_glossary.csv"
        
        if personal_file.exists():
            try:
                glossary_dict = self.load_glossary_from_csv(personal_file)
                return GlossaryFile(
                    id=f"personal_{username}",
                    name="Personal Glossary",
                    file_path=str(personal_file),
                    owner=username,
                    is_global=False,
                    created_at=datetime.fromtimestamp(personal_file.stat().st_ctime),
                    updated_at=datetime.fromtimestamp(personal_file.stat().st_mtime),
                    item_count=len(glossary_dict),
                    description="User personal glossary"
                )
            except Exception as e:
                logger.error(LogModule.GLOSSARY, f"Failed to get user personal glossary {username}: {e}")
        return None
    
    def get_user_selection(self, username: str) -> UserGlossarySelection:
        """Get user glossary selection"""
        selection_data = self.user_selections.get(username, {})
        return UserGlossarySelection(
            username=username,
            selected_global_glossaries=selection_data.get('selected_global_glossaries', []),
            personal_glossary=selection_data.get('personal_glossary')
        )
    
    def save_user_selection(self, selection: UserGlossarySelection):
        """Save user glossary selection"""
        self.user_selections[selection.username] = {
            'selected_global_glossaries': selection.selected_global_glossaries,
            'personal_glossary': selection.personal_glossary
        }
        self._save_user_selections()
    
    def create_global_glossary(
        self, 
        name: str, 
        glossary_dict: Dict[str, str], 
        owner: str,
        description: Optional[str] = None
    ) -> GlossaryFile:
        """Create global glossary"""
        # Generate unique filename (avoid overwriting with same name): name_timestamp[(_shortUID)].csv
        safe_name = "".join(c for c in name if c.isalnum() or c in (' ', '-', '_')).rstrip()
        safe_name = safe_name.replace(' ', '_')
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        file_path = f"{safe_name}_{timestamp}.csv"
        full_path = self.global_dir / file_path
        # If still conflicting in extreme cases, append short UID
        if full_path.exists():
            short_uid = uuid.uuid4().hex[:6]
            file_path = f"{safe_name}_{timestamp}_{short_uid}.csv"
            full_path = self.global_dir / file_path
        
        # Save file
        self.save_glossary_to_csv(glossary_dict, full_path)
        
        # Create metadata
        glossary_id = f"global_{int(time.time())}"
        now = datetime.now()
        
        glossary_metadata = {
            'name': name,
            'file_path': file_path,
            'owner': owner,
            'created_at': now.isoformat(),
            'updated_at': now.isoformat(),
            'description': description
        }
        
        self.global_glossaries[glossary_id] = glossary_metadata
        self._save_global_glossaries()
        
        # Update version
        self.update_glossary_version(glossary_id, owner)
        
        return GlossaryFile(
            id=glossary_id,
            name=name,
            file_path=str(full_path),
            owner=owner,
            is_global=True,
            created_at=now,
            updated_at=now,
            item_count=len(glossary_dict),
            description=description
        )
    
    def update_global_glossary(
        self, 
        glossary_id: str, 
        glossary_dict: Dict[str, str], 
        updated_by: str
    ) -> bool:
        """Update global glossary"""
        if glossary_id not in self.global_glossaries:
            return False
        
        metadata = self.global_glossaries[glossary_id]
        file_path = self.global_dir / metadata['file_path']
        
        # Save file
        self.save_glossary_to_csv(glossary_dict, file_path)
        
        # Update metadata
        metadata['updated_at'] = datetime.now().isoformat()
        self._save_global_glossaries()
        
        # Update version
        self.update_glossary_version(glossary_id, updated_by)
        
        return True
    
    def delete_global_glossary(self, glossary_id: str) -> bool:
        """Delete global glossary"""
        if glossary_id not in self.global_glossaries:
            return False
        
        metadata = self.global_glossaries[glossary_id]
        file_path = self.global_dir / metadata['file_path']
        
        # Delete file
        if file_path.exists():
            file_path.unlink()
        
        # Delete metadata
        del self.global_glossaries[glossary_id]
        self._save_global_glossaries()
        
        # Delete version information
        if glossary_id in self.versions:
            del self.versions[glossary_id]
            self._save_versions()
        
        # Re-verify and clean up residues
        try:
            self.reconcile_metadata()
        except Exception as _e:
            logger.warning(LogModule.GLOSSARY, f"Glossary metadata self-check failed after deletion: {_e}")
        
        return True

    def reconcile_metadata(self):
        """Align metadata with actual files:
        - Remove items in global_glossaries that point to non-existent files
        - Remove non-existent glossary_id in versions
        """
        # Clean up global glossary metadata
        removed_ids: List[str] = []
        for glossary_id, meta in list(self.global_glossaries.items()):
            file_path = self.global_dir / meta.get('file_path', '')
            if not file_path.exists():
                removed_ids.append(glossary_id)
                del self.global_glossaries[glossary_id]
        if removed_ids:
            logger.info(LogModule.GLOSSARY, f"Cleaned up invalid glossary metadata: {removed_ids}")
            self._save_global_glossaries()
        
        # Clean up version information
        removed_version_ids: List[str] = []
        for glossary_id in list(self.versions.keys()):
            if glossary_id not in self.global_glossaries and not glossary_id.startswith('personal_'):
                removed_version_ids.append(glossary_id)
                del self.versions[glossary_id]
        if removed_version_ids:
            logger.info(LogModule.GLOSSARY, f"Cleaned up invalid glossary version information: {removed_version_ids}")
            self._save_versions()
    
    def save_user_personal_glossary(
        self, 
        username: str, 
        glossary_dict: Dict[str, str]
    ) -> bool:
        """Save user personal glossary"""
        user_dir = self.users_dir / username
        user_dir.mkdir(parents=True, exist_ok=True)
        
        personal_file = user_dir / "personal_glossary.csv"
        self.save_glossary_to_csv(glossary_dict, personal_file)
        
        # Update version
        personal_id = f"personal_{username}"
        self.update_glossary_version(personal_id, username)
        
        return True


# Global storage instance
_glossary_storage = None


def get_glossary_storage() -> GlossaryStorage:
    """Get glossary storage instance"""
    global _glossary_storage
    if _glossary_storage is None:
        _glossary_storage = GlossaryStorage()
    return _glossary_storage
