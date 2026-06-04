import copy
import json
import os
import secrets
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Dict, Optional, Tuple
import hashlib

from logger.logger import LogModule
from backend.logger import unified_logger as logger


class LocalUserRole(str, Enum):
    SUPER_ADMIN = "super_admin"    # Super admin (highest level)
    ADMIN = "admin"                # Full admin (cannot change super admin password)
    LOCAL_ADMIN = "local_admin"    # Local admin
    APP_ADMIN = "app_admin"        # Manage prompts and glossary
    LOCAL_USER = "local_user"      # Local user
    USER = "user"                 # Regular user


@dataclass
class LocalUser:
    username: str
    password_hash: str  # stored as: pbkdf2_sha256$iterations$salt_hex$hash_hex
    role: LocalUserRole
    display_name: Optional[str] = None
    email: Optional[str] = None


class LocalUserStore:
    """Manages local users with secure password hashing and JSON persistence.

    Search/Write priority similar to SecretsManager:
    1) /etc/Owlangs/local_users.json if directory exists
    2) Executable directory (when frozen)
    3) Project root (repo root)
    """

    def __init__(self, filename: str = "local_users.json") -> None:
        system_dir = Path("/etc/Owlangs")
        system_file = system_dir / filename
        self.file_path: Path
        if system_dir.exists() and system_file.exists():
            self.file_path = system_file
            logger.info(LogModule.AUTH, f"[LocalUsers] Using system users file: {self.file_path}")
        else:
            import sys
            if getattr(sys, 'frozen', False):
                # Windows deployment: use shared app data dir (C:\ProgramData\Owlangs)
                # instead of Program Files which requires admin privileges
                if os.name == 'nt':
                    from backend.utils.path_utils import get_system_data_dir
                    self.file_path = Path(get_system_data_dir()) / filename
                    logger.info(LogModule.AUTH, f"[LocalUsers] Using Windows data users file: {self.file_path}")
                else:
                    # macOS/Linux: use system data dir
                    from backend.utils.path_utils import get_system_data_dir
                    self.file_path = Path(get_system_data_dir()) / filename
                    logger.info(LogModule.AUTH, f"[LocalUsers] Using system data users file: {self.file_path}")
            else:
                # repo root
                repo_root = Path(__file__).resolve().parents[2]
                self.file_path = (Path(filename) if Path(filename).is_absolute() else (repo_root / filename))
                logger.info(LogModule.AUTH, f"[LocalUsers] Using repo users file: {self.file_path}")
        self._cache: Optional[Dict[str, Dict]] = None

    # ===== Password hashing =====
    @staticmethod
    def _hash_password(password: str, iterations: int = None) -> str:
        """Hash password using unified password manager"""
        from .password_manager import password_manager
        return password_manager.hash_password(password, iterations)

    @staticmethod
    def _verify_password(password: str, encoded: str) -> bool:
        """Verify password using unified password manager"""
        from .password_manager import password_manager
        return password_manager.verify_password(password, encoded)

    # ===== Persistence =====
    def _load(self) -> Dict[str, Dict]:
        if self._cache is not None:
            return self._cache
        if not self.file_path.exists():
            logger.warning(LogModule.AUTH, f"[LocalUsers] Users file not found: {self.file_path}, using empty store")
            self._cache = {"_meta": {"version": 1}, "users": {}}
            return self._cache
        try:
            with open(self.file_path, 'r', encoding='utf-8-sig') as f:
                data = json.load(f)
            if not isinstance(data, dict):
                data = {"_meta": {"version": 1}, "users": {}}
            data.setdefault("_meta", {"version": 1})
            data.setdefault("users", {})
            self._cache = data
            logger.info(LogModule.AUTH, f"[LocalUsers] Loaded {len(self._cache['users'])} local users")
            return self._cache
        except Exception as e:
            logger.error(LogModule.AUTH, f"[LocalUsers] Failed to load users file: {e}")
            self._cache = {"_meta": {"version": 1}, "users": {}}
            return self._cache

    def _save(self, data: Dict) -> bool:
        try:
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            self._cache = data
            # set safe permissions for system dir
            try:
                if str(self.file_path).startswith('/etc/Owlangs'):
                    os.chmod(self.file_path, 0o640)
            except Exception:
                pass
            # CRITICAL: Invalidate UnifiedUserStore cache so that auth/login
            # picks up local-user mutations immediately instead of stale data.
            try:
                from .unified_user_store import get_unified_user_store
                unified_store = get_unified_user_store()
                unified_store._cache = None
                logger.info(LogModule.AUTH, "[LocalUsers] Invalidated UnifiedUserStore cache after save")
            except Exception:
                pass
            logger.info(LogModule.AUTH, f"[LocalUsers] Saved users file to: {self.file_path}")
            return True
        except Exception as e:
            logger.error(LogModule.AUTH, f"[LocalUsers] Failed to save users file: {e}")
            return False

    # ===== CRUD =====
    def list_users(self) -> Dict[str, Dict]:
        users_data = self._load().get("users", {})
        # Handle both array and object formats
        if isinstance(users_data, list):
            # Convert array to dict format
            users_dict = {}
            for user in users_data:
                if isinstance(user, dict) and "username" in user:
                    username = user["username"]
                    users_dict[username] = user
            return users_dict
        return users_data

    def get_user(self, username: str) -> Optional[LocalUser]:
        users_data = self._load().get("users", {})
        data = None
        
        # Handle both array and object formats
        if isinstance(users_data, list):
            # Find user in array
            for user in users_data:
                if isinstance(user, dict) and user.get("username") == username:
                    data = user
                    break
        else:
            # Handle object format
            data = users_data.get(username)
            
        if not data:
            return None
        try:
            return LocalUser(
                username=username,
                password_hash=data.get("password_hash", ""),
                role=LocalUserRole(data.get("role", LocalUserRole.USER)),
                display_name=data.get("display_name"),
                email=data.get("email")
            )
        except Exception:
            return None

    def create_user(self, username: str, password: str, role: LocalUserRole, display_name: Optional[str] = None, email: Optional[str] = None) -> bool:
        users = copy.deepcopy(self._load())
        users_list = users.get("users", [])
        password_hash = self._hash_password(password)

        # Support both object and array storage formats for backward compatibility
        if isinstance(users_list, list):
            # Check duplicate
            for user in users_list:
                if isinstance(user, dict) and user.get("username") == username:
                    raise ValueError("User already exists")
            # Append new user object entry
            users_list.append({
                "username": username,
                "password_hash": password_hash,
                "role": role.value,
                "display_name": display_name or username,
                "email": email or None
            })
            users["users"] = users_list
        else:
            # Dict format { username: { ... } }
            if username in users_list:
                raise ValueError("User already exists")
            users_list[username] = {
                "password_hash": password_hash,
                "role": role.value,
                "display_name": display_name or username,
                "email": email or None
            }
            users["users"] = users_list

        return self._save(users)

    def update_user(self, username: str, role: Optional[LocalUserRole] = None, display_name: Optional[str] = None, email: Optional[str] = None) -> bool:
        users = copy.deepcopy(self._load())
        users_list = users.get("users", [])
        
        # Handle both array and object formats
        if isinstance(users_list, list):
            # Find user in array
            user_found = False
            for user in users_list:
                if isinstance(user, dict) and user.get("username") == username:
                    user_found = True
                    if role is not None:
                        user["role"] = role.value
                    if display_name is not None:
                        user["display_name"] = display_name
                    if email is not None:
                        user["email"] = email
                    break
            if not user_found:
                raise ValueError("User not found")
        else:
            # Handle object format
            if username not in users_list:
                raise ValueError("User not found")
            u = users_list[username]
            if role is not None:
                u["role"] = role.value
            if display_name is not None:
                u["display_name"] = display_name
            if email is not None:
                u["email"] = email
                
        return self._save(users)

    def reset_password(self, username: str, new_password: str) -> bool:
        users = copy.deepcopy(self._load())
        users_list = users.get("users", [])
        
        # Handle both array and object formats
        if isinstance(users_list, list):
            # Find user in array
            user_found = False
            for user in users_list:
                if isinstance(user, dict) and user.get("username") == username:
                    user_found = True
                    user["password_hash"] = self._hash_password(new_password)
                    break
            if not user_found:
                raise ValueError("User not found")
        else:
            # Handle object format
            if username not in users_list:
                raise ValueError("User not found")
            users_list[username]["password_hash"] = self._hash_password(new_password)
            
        return self._save(users)

    def delete_user(self, username: str) -> bool:
        users = copy.deepcopy(self._load())
        users_list = users.get("users", [])
        
        # Handle both array and object formats
        if isinstance(users_list, list):
            # Find and remove user from array
            for i, user in enumerate(users_list):
                if isinstance(user, dict) and user.get("username") == username:
                    users_list.pop(i)
                    return self._save(users)
            return True  # User not found, consider it deleted
        else:
            # Handle object format
            if username in users_list:
                del users_list[username]
                return self._save(users)
            return True

    # ===== Auth =====
    def verify_credentials(self, username: str, password: str) -> Tuple[bool, Optional[LocalUser]]:
        user = self.get_user(username)
        if not user:
            return False, None
        ok = self._verify_password(password, user.password_hash)
        return ok, user if ok else None

    # ===== Template =====
    def ensure_template(self) -> Path:
        template = self.file_path.parent / f"{self.file_path.stem}.template"
        if template.exists():
            return template
        data = {
            "_comment": "Local users template - copy to local_users.json and edit.",
            "_warning": "Do not commit this file to git.",
            "_meta": {"version": 1},
            "users": {
                "editor": {
                    "password_hash": self._hash_password("change_me_please"),
                    "role": LocalUserRole.APP_ADMIN.value,
                    "display_name": "Editor",
                    "email": ""
                }
            }
        }
        try:
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(template, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.info(LogModule.AUTH, f"[LocalUsers] Created template: {template}")
            return template
        except Exception as e:
            logger.error(LogModule.AUTH, f"[LocalUsers] Failed to create template: {e}")
            return template


# Singleton accessor
_local_users_store: Optional[LocalUserStore] = None

def get_local_user_store() -> LocalUserStore:
    global _local_users_store
    if _local_users_store is None:
        _local_users_store = LocalUserStore()
    return _local_users_store
