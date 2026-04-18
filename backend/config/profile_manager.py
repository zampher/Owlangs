# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

import os
import json
import shutil
from pathlib import Path
from typing import List, Dict, Any

from logger import unified_logger as logger
from logger.logger import LogModule

class ProfileManager:
    """Configuration manager for managing user configuration templates and actual configurations"""
    
    def __init__(self, 
                 templates_dir: str = "templates",
                 profiles_dir: str = "../../user_profiles"):
        self.templates_dir = Path(templates_dir)
        self.profiles_dir = Path(profiles_dir)
        
        # Ensure directories exist
        self.templates_dir.mkdir(parents=True, exist_ok=True)
        self.profiles_dir.mkdir(parents=True, exist_ok=True)
    
    def get_template_path(self, template_name: str = "default") -> Path:
        """Get template file path"""
        return self.templates_dir / f"{template_name}_profile.json"
    
    def get_profile_path(self, username: str) -> Path:
        """Get user configuration file path"""
        return self.profiles_dir / f"{username}_profile.json"
    
    def list_templates(self) -> List[str]:
        """List all available configuration templates"""
        templates = []
        if self.templates_dir.exists():
            for file in self.templates_dir.glob("*_profile.json"):
                template_name = file.stem.replace("_profile", "")
                templates.append(template_name)
        return templates
    
    def list_profiles(self) -> List[str]:
        """List all user configurations"""
        profiles = []
        if self.profiles_dir.exists():
            for file in self.profiles_dir.glob("*_profile.json"):
                username = file.stem.replace("_profile", "")
                profiles.append(username)
        return profiles
    
    def create_profile_from_template(self, username: str, template_name: str = "default") -> bool:
        """Create user configuration from template"""
        # Use unified default template
        
        template_path = self.get_template_path(template_name)
        profile_path = self.get_profile_path(username)
        
        if not template_path.exists():
            logger.error(LogModule.CONFIG, f"Template file does not exist: {template_path}")
            return False
        
        try:
            # Copy template file to user configuration directory
            shutil.copy2(template_path, profile_path)
            logger.info(LogModule.CONFIG, f"Created configuration for user {username} from template {template_name}")
            return True
        except Exception as e:
            logger.error(LogModule.CONFIG, f"Failed to create user configuration: {e}")
            return False
    
    def delete_profile(self, username: str) -> bool:
        """Delete user configuration"""
        profile_path = self.get_profile_path(username)
        
        if not profile_path.exists():
            logger.warning(LogModule.CONFIG, f"User configuration does not exist: {profile_path}")
            return False
        
        try:
            profile_path.unlink()
            logger.info(LogModule.CONFIG, f"Deleted configuration for user {username}")
            return True
        except Exception as e:
            logger.error(LogModule.CONFIG, f"Failed to delete user configuration: {e}")
            return False
    
    def backup_profile(self, username: str, backup_dir: str = "backups") -> bool:
        """Backup user configuration"""
        profile_path = self.get_profile_path(username)
        backup_path = Path(backup_dir)
        backup_path.mkdir(parents=True, exist_ok=True)
        
        if not profile_path.exists():
            logger.warning(LogModule.CONFIG, f"User configuration does not exist: {profile_path}")
            return False
        
        try:
            backup_file = backup_path / f"{username}_profile_backup.json"
            shutil.copy2(profile_path, backup_file)
            logger.info(LogModule.CONFIG, f"Backed up configuration for user {username} to {backup_file}")
            return True
        except Exception as e:
            logger.error(LogModule.CONFIG, f"Failed to backup user configuration: {e}")
            return False
    
    def restore_profile(self, username: str, backup_dir: str = "backups") -> bool:
        """Restore user configuration from backup"""
        backup_path = Path(backup_dir) / f"{username}_profile_backup.json"
        profile_path = self.get_profile_path(username)
        
        if not backup_path.exists():
            logger.error(LogModule.CONFIG, f"Backup file does not exist: {backup_path}")
            return False
        
        try:
            shutil.copy2(backup_path, profile_path)
            logger.info(LogModule.CONFIG, f"Restored configuration for user {username} from backup")
            return True
        except Exception as e:
            logger.error(LogModule.CONFIG, f"Failed to restore user configuration: {e}")
            return False
    
    def get_profile_info(self, username: str) -> Dict[str, Any]:
        """Get user configuration information"""
        profile_path = self.get_profile_path(username)
        
        if not profile_path.exists():
            return {"exists": False}
        
        try:
            with open(profile_path, 'r', encoding='utf-8-sig') as f:
                data = json.load(f)
            
            # Get file information
            stat = profile_path.stat()
            
            return {
                "exists": True,
                "size": stat.st_size,
                "created": stat.st_ctime,
                "modified": stat.st_mtime,
                "settings_count": len(data),
                "has_created_at": "created_at" in data,
                "has_updated_at": "updated_at" in data
            }
        except Exception as e:
            logger.error(LogModule.CONFIG, f"Failed to get user configuration information: {e}")
            return {"exists": False, "error": str(e)}
    
    def validate_profile(self, username: str) -> Dict[str, Any]:
        """Validate user configuration integrity"""
        profile_path = self.get_profile_path(username)
        
        if not profile_path.exists():
            return {"valid": False, "error": "Configuration file does not exist"}
        
        try:
            with open(profile_path, 'r', encoding='utf-8-sig') as f:
                data = json.load(f)
            
            # Check required fields
            required_fields = [
                "ui_language", "translator_last_workflow", "translator_target_language",
                "translator_temperature", "theme"
            ]
            
            missing_fields = []
            for field in required_fields:
                if field not in data:
                    missing_fields.append(field)
            
            return {
                "valid": len(missing_fields) == 0,
                "missing_fields": missing_fields,
                "total_fields": len(data)
            }
        except Exception as e:
            return {"valid": False, "error": str(e)}


def main():
    """Command line tool entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="User configuration management tool")
    parser.add_argument("action", choices=["list", "create", "delete", "backup", "restore", "info", "validate"],
                       help="Operation type")
    parser.add_argument("--username", help="Username")
    parser.add_argument("--template", default="default", help="Template name (default: default)")
    parser.add_argument("--backup-dir", default="backups", help="Backup directory")
    
    args = parser.parse_args()
    
    manager = ProfileManager()
    
    if args.action == "list":
        print("Available templates:", manager.list_templates())
        print("User configurations:", manager.list_profiles())
    
    elif args.action == "create":
        if not args.username:
            print("Error: Username must be specified")
            return
        success = manager.create_profile_from_template(args.username, args.template)
        print(f"Create configuration: {'Success' if success else 'Failed'}")
    
    elif args.action == "delete":
        if not args.username:
            print("Error: Username must be specified")
            return
        success = manager.delete_profile(args.username)
        print(f"Delete configuration: {'Success' if success else 'Failed'}")
    
    elif args.action == "backup":
        if not args.username:
            print("Error: Username must be specified")
            return
        success = manager.backup_profile(args.username, args.backup_dir)
        print(f"Backup configuration: {'Success' if success else 'Failed'}")
    
    elif args.action == "restore":
        if not args.username:
            print("Error: Username must be specified")
            return
        success = manager.restore_profile(args.username, args.backup_dir)
        print(f"Restore configuration: {'Success' if success else 'Failed'}")
    
    elif args.action == "info":
        if not args.username:
            print("Error: Username must be specified")
            return
        info = manager.get_profile_info(args.username)
        print(json.dumps(info, indent=2, ensure_ascii=False))
    
    elif args.action == "validate":
        if not args.username:
            print("Error: Username must be specified")
            return
        result = manager.validate_profile(args.username)
        print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
