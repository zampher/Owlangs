# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

import json
import os
import base64
import hashlib
from datetime import date
from pathlib import Path
from typing import Dict, Any, Optional

from logger import unified_logger as logger
from logger.logger import LogModule


class SecretsManager:
    """Sensitive configuration manager - manages API keys and other sensitive information"""
    
    def __init__(self, secrets_file: str = "secrets.json"):
        """
        Initialize sensitive configuration manager
        
        Args:
            secrets_file: Sensitive configuration file path (filename only, will be resolved via configs directory)
        """
        from utils.path_utils import get_config_file_path, get_template_file_path
        
        # Use unified config path function (prioritizes configs directory)
        self.secrets_file = get_config_file_path(secrets_file)
        
        # If secrets file doesn't exist, try to create from template
        if not self.secrets_file.exists():
            template_file = get_template_file_path(f"{secrets_file}.template")
            if template_file.exists():
                try:
                    import shutil
                    # Ensure configs directory exists
                    self.secrets_file.parent.mkdir(parents=True, exist_ok=True)
                    # Copy template to create secrets file
                    shutil.copy2(template_file, self.secrets_file)
                    # Set conservative permissions: rw-r----- (0640)
                    try:
                        os.chmod(self.secrets_file, 0o640)
                    except Exception:
                        pass
                    logger.info(
                        LogModule.CONFIG,
                        f"Created {self.secrets_file} from template {template_file}",
                    )
                except Exception as copy_err:
                    logger.warning(
                        LogModule.CONFIG,
                        f"Failed to create secrets file from template: {copy_err}. Using empty configuration.",
                    )
        
        # When upgrading, template structure may add new keys.
        # Attempt to merge existing secrets.json with the latest template:
        #   - 保留旧文件中的实际 KEY 值（API Key、MinerU Token 等）
        #   - 从模板补充新增加的配置结构/字段，避免升级后缺少必要配置
        try:
            self._maybe_merge_with_template()
        except Exception as merge_err:
            logger.warning(
                LogModule.CONFIG,
                f"Failed to merge secrets.json with template: {merge_err}",
            )
        
        logger.debug(LogModule.CONFIG, f"Using secrets config: {self.secrets_file}")
        self._secrets_cache: Optional[Dict[str, Any]] = None
        self._load_failed: bool = False
        self._load_failed_reason: Optional[str] = None
        
    def load_secrets(self) -> Dict[str, Any]:
        """
        Load sensitive configuration
        
        Returns:
            Sensitive configuration dictionary, returns empty dictionary if file does not exist
        """
        if self._secrets_cache is not None:
            return self._secrets_cache
        
        if not self.secrets_file.exists():
            # In PyInstaller environment, avoid pointing to /tmp/_MEI* directory
            try:
                import sys as _sm_sys
                if getattr(_sm_sys, 'frozen', False):
                    exe_dir = Path(os.path.dirname(_sm_sys.executable))
                    fallback = exe_dir / self.secrets_file.name
                    if fallback != self.secrets_file:
                        logger.debug(LogModule.CONFIG, f"Secrets file not found at {self.secrets_file}, trying executable dir: {fallback}")
                        if fallback.exists():
                            self.secrets_file = fallback
            except Exception:
                pass

        if not self.secrets_file.exists():
            logger.warning(LogModule.CONFIG, f"Secrets file {self.secrets_file} not found, using empty configuration")
            self._secrets_cache = {}
            self._load_failed = False
            return self._secrets_cache
            
        try:
            with open(self.secrets_file, 'r', encoding='utf-8-sig') as f:
                secrets = json.load(f)

            # Normalize structure: add configured attribute for api keys and mineru token (backward compatibility)
            try:
                changed = False
                # Platform API Keys (support both new "api_keys" and old "platform_api_keys")
                api_keys_dict = secrets.get("api_keys", secrets.get("platform_api_keys"))
                if api_keys_dict is None and "platform_api_keys" in secrets:
                    api_keys_dict = secrets["platform_api_keys"]
                elif api_keys_dict is None:
                    api_keys_dict = {}
                
                # Normalize api_keys structure
                pak = api_keys_dict
                if isinstance(pak, dict):
                    for platform, val in list(pak.items()):
                        if isinstance(val, str):
                            pak[platform] = {"key": val, "configured": bool(val)}
                            changed = True
                        elif isinstance(val, dict):
                            # Ensure fields exist
                            if "key" not in val:
                                val["key"] = ""
                                changed = True
                            if "configured" not in val:
                                val["configured"] = bool(val.get("key"))
                                changed = True
                
                # Ensure api_keys exists in new format
                if "api_keys" not in secrets and pak:
                    secrets["api_keys"] = pak
                    changed = True
                
                # MinerU Token (support both new "mineru_token" and old "translator_mineru_token")
                mineru_token_val = secrets.get("mineru_token", secrets.get("translator_mineru_token"))
                if mineru_token_val is None:
                    if "translator_mineru_token" in secrets:
                        mineru_token_val = secrets["translator_mineru_token"]
                
                if isinstance(mineru_token_val, str):
                    mt_dict = {
                        "key": mineru_token_val,
                        "configured": bool(mineru_token_val)
                    }
                    secrets["mineru_token"] = mt_dict
                    # Also update old key for compatibility
                    if "translator_mineru_token" not in secrets or secrets.get("translator_mineru_token") != mt_dict:
                        secrets["translator_mineru_token"] = mt_dict
                    changed = True
                elif isinstance(mineru_token_val, dict):
                    mt = mineru_token_val
                    if "key" not in mt:
                        mt["key"] = ""
                        changed = True
                    if "configured" not in mt:
                        mt["configured"] = bool(mt.get("key"))
                        changed = True
                    # Ensure mineru_token exists in new format
                    if "mineru_token" not in secrets:
                        secrets["mineru_token"] = mt
                        changed = True

                # MinerU Local Token (for self-hosted MinerU instances)
                mineru_local_val = secrets.get("mineru_local_token")
                if isinstance(mineru_local_val, str):
                    mtl_dict = {
                        "key": mineru_local_val,
                        "configured": bool(mineru_local_val)
                    }
                    secrets["mineru_local_token"] = mtl_dict
                    changed = True
                elif isinstance(mineru_local_val, dict):
                    mtl = mineru_local_val
                    if "key" not in mtl:
                        mtl["key"] = ""
                        changed = True
                    if "configured" not in mtl:
                        mtl["configured"] = bool(mtl.get("key"))
                        changed = True
                else:
                    # Initialize with empty value if not exists
                    secrets["mineru_local_token"] = {"key": "", "configured": False}
                    changed = True

                # Normalize donor activation: store in obfuscated structure "__da"
                # and avoid exposing clear-text field names in secrets.json.
                # Legacy plain structure "donor_activation" is still read for backward compatibility.
                obf = secrets.get("__da")
                legacy = secrets.get("donor_activation")
                activated_val: bool = False
                license_token_val: Optional[str] = None
                trial_start_plain: Optional[str] = None

                # Prefer obfuscated structure if present
                if isinstance(obf, dict):
                    try:
                        f_flag = bool(obf.get("f", False))
                        t_val = obf.get("t")
                        s_val = obf.get("s")
                        decoded = self._decode_trial_date_obfuscated(s_val) if isinstance(s_val, str) else None
                        activated_val = f_flag
                        license_token_val = t_val
                        trial_start_plain = decoded
                    except Exception:
                        # Fall back to legacy structure if decode fails
                        pass

                # Fallback: read legacy clear structure
                if trial_start_plain is None and isinstance(legacy, dict):
                    activated_val = bool(legacy.get("activated", activated_val))
                    license_token_val = legacy.get("license_token", license_token_val)
                    ts = legacy.get("trial_start_date")
                    if isinstance(ts, str) and ts:
                        trial_start_plain = ts

                # Initialize trial_start_plain if still missing (use trial anchor so reinstall does not reset trial)
                if not trial_start_plain:
                    try:
                        from utils.donor_trial import get_effective_trial_start
                        trial_start_plain = get_effective_trial_start(None)
                    except Exception:
                        trial_start_plain = date.today().isoformat()
                else:
                    try:
                        from utils.donor_trial import write_trial_anchor
                        write_trial_anchor(trial_start_plain)
                    except Exception:
                        pass

                # Write back obfuscated structure
                secrets["__da"] = {
                    "f": bool(activated_val),
                    "t": license_token_val,
                    "s": self._encode_trial_date_obfuscated(trial_start_plain),
                }
                # Remove legacy clear-text donor_activation to avoid exposing obvious labels
                if "donor_activation" in secrets:
                    del secrets["donor_activation"]
                changed = True

                if changed:
                    logger.debug(LogModule.CONFIG, f"Normalized secrets structure, saving updated file")
                    # Save immediately to ensure file is written with new structure
                    self._secrets_cache = secrets
                    self.save_secrets(secrets)
            except Exception:
                # Normalization failure does not affect reading
                pass
            
            logger.debug(LogModule.CONFIG, f"Successfully loaded sensitive configuration file: {self.secrets_file}")
            self._secrets_cache = secrets
            self._load_failed = False
            self._load_failed_reason = None
            return secrets
            
        except Exception as e:
            logger.error(LogModule.CONFIG, f"Failed to load sensitive configuration file: {e}")
            self._secrets_cache = {}
            self._load_failed = True
            self._load_failed_reason = str(e)
            return self._secrets_cache

    def _encode_trial_date_obfuscated(self, plain_date: str) -> str:
        """
        Obfuscate trial_start_date for storage in secrets.json.

        Scheme:
            data = plain_date.encode('utf-8')
            tag = first 4 bytes of sha256(b"owlangs-trial" + data)
            store = base64.urlsafe_b64encode(tag + data).decode('ascii')

        This is NOT strong cryptography, just enough to avoid exposing
        clear-text dates and field intent at a glance.
        """
        try:
            data = plain_date.encode("utf-8")
            h = hashlib.sha256(b"owlangs-trial" + data).digest()[:4]
            blob = h + data
            return base64.urlsafe_b64encode(blob).decode("ascii")
        except Exception:
            # Fallback: return plain text if obfuscation fails
            return plain_date

    def _decode_trial_date_obfuscated(self, encoded: Optional[str]) -> Optional[str]:
        """
        Decode obfuscated trial_start_date.

        Returns:
            Plain ISO date string or None if decoding/validation fails.
        """
        if not encoded or not isinstance(encoded, str):
            return None
        try:
            blob = base64.urlsafe_b64decode(encoded.encode("ascii"))
            if len(blob) <= 4:
                return None
            tag = blob[:4]
            data = blob[4:]
            expected_tag = hashlib.sha256(b"owlangs-trial" + data).digest()[:4]
            if tag != expected_tag:
                return None
            return data.decode("utf-8")
        except Exception:
            return None

    def _maybe_merge_with_template(self) -> None:
        """
        Merge existing secrets.json with template structure if both exist.
        
        设计目标：
        - 升级后如果 secrets.json.template 增加了新配置字段/结构，
          在不丢失用户已有 KEY 的前提下，把这些新结构合并进现有 secrets.json。
        - 行为等价于：以模板为“结构蓝本”，用旧 secrets.json 中的真实值覆盖同名字段，
          同时保留旧文件里模板不存在的额外字段。
        """
        from utils.path_utils import get_template_file_path

        # 只有在 secrets 文件已经存在时才需要做模板合并
        if not self.secrets_file.exists():
            return

        template_path = get_template_file_path(f"{self.secrets_file.name}.template")
        if not template_path.exists():
            return

        try:
            with open(template_path, "r", encoding="utf-8-sig") as tf:
                template_data = json.load(tf)
        except Exception as e:
            logger.warning(
                LogModule.CONFIG,
                f"Failed to load secrets template {template_path}: {e}",
            )
            return

        try:
            with open(self.secrets_file, "r", encoding="utf-8-sig") as cf:
                current_data = json.load(cf)
        except Exception:
            # 如果当前文件无法解析，就不做合并，交由 load_secrets 的容错逻辑处理
            return

        if not isinstance(template_data, dict) or not isinstance(current_data, dict):
            # 模板或现有文件不是 dict 结构时，不做复杂合并
            return

        def _merge(template_val: Any, current_val: Any) -> Any:
            # 双方都是 dict：按 key 递归合并
            if isinstance(template_val, dict) and isinstance(current_val, dict):
                merged: Dict[str, Any] = {}
                # 先遍历模板中的 key：保证新结构完整
                for k, tv in template_val.items():
                    if k in current_val:
                        merged[k] = _merge(tv, current_val[k])
                    else:
                        merged[k] = tv
                # 再把旧文件中“模板里没有”的额外 key 也保留下来
                for k, cv in current_val.items():
                    if k not in merged:
                        merged[k] = cv
                return merged

            # 其他情况：优先保留旧文件中的实际值，如果旧值为 None，再回退到模板的默认值
            if current_val is not None:
                return current_val
            return template_val

        merged = _merge(template_data, current_data)

        # 如果合并后与原数据一致，则无需写回
        if merged == current_data:
            return

        # 写回合并后的结构，但不刷新 cache（cache 会在首次 load_secrets 时填充）
        try:
            self.secrets_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.secrets_file, "w", encoding="utf-8") as f:
                json.dump(merged, f, indent=2, ensure_ascii=False)
            logger.info(
                LogModule.CONFIG,
                f"Merged existing secrets.json with template structure: {self.secrets_file}",
            )
        except Exception as e:
            logger.error(
                LogModule.CONFIG,
                f"Failed to save merged secrets.json structure: {e}",
            )
    
    def get_api_key(self, platform: str) -> Optional[str]:
        """
        Get API key for a single platform by name.

        Handles MinerU special tokens (mineru_token, mineru_local_token)
        and falls back to the generic api_keys dict for other platforms.

        Args:
            platform: Platform name (e.g. "mineru", "paddle", "openai")

        Returns:
            API key string or None if not configured
        """
        if platform == "mineru":
            return self.get_mineru_token()
        if platform == "mineru_local":
            return self.get_mineru_local_token()
        return self.get_api_keys().get(platform)

    def get_api_keys(self) -> Dict[str, str]:
        """
        Get API key configuration

        Returns:
            API key dictionary
        """
        secrets = self.load_secrets()
        # Support both new key (api_keys) and old key (platform_api_keys) for backward compatibility
        raw = secrets.get("api_keys", secrets.get("platform_api_keys", {}))
        # Compatibility: return platform->string
        result: Dict[str, str] = {}
        if isinstance(raw, dict):
            for platform, val in raw.items():
                if isinstance(val, dict):
                    result[platform] = val.get("key", "")
                else:
                    result[platform] = str(val) if val is not None else ""
        return result

    def get_api_keys_meta(self) -> Dict[str, Dict[str, Any]]:
        """
        Return platform API Key metadata { platform: { key: str, configured: bool } }
        Includes both AI platforms and MinerU
        """
        secrets = self.load_secrets()
        meta: Dict[str, Dict[str, Any]] = {}
        
        # Get AI platform API keys (support both new key "api_keys" and old key "platform_api_keys")
        pak = secrets.get("api_keys", secrets.get("platform_api_keys", {}))
        if isinstance(pak, dict):
            for platform, val in pak.items():
                if isinstance(val, dict):
                    meta[platform] = {
                        "key": val.get("key", ""),
                        "configured": bool(val.get("configured", bool(val.get("key"))))
                    }
                else:
                    key = str(val) if val is not None else ""
                    meta[platform] = {"key": key, "configured": bool(key)}
        
        # Get MinerU token and merge into platform_api_keys
        mineru_token = self.get_mineru_token()
        if mineru_token:
            meta["mineru"] = {
                "key": mineru_token,
                "configured": True
            }
        else:
            meta["mineru"] = {
                "key": "",
                "configured": False
            }
        
        # Get MinerU Local token and merge into platform_api_keys
        mineru_local_token = self.get_mineru_local_token()
        if mineru_local_token:
            meta["mineru_local"] = {
                "key": mineru_local_token,
                "configured": True
            }
        else:
            meta["mineru_local"] = {
                "key": "",
                "configured": False
            }
        
        return meta
    
    def get_mineru_token(self) -> Optional[str]:
        """
        Get MinerU token
        
        Returns:
            MinerU token, returns None if not exists
        """
        secrets = self.load_secrets()
        # Support both new key (mineru_token) and old key (translator_mineru_token)
        val = secrets.get("mineru_token", secrets.get("translator_mineru_token"))
        if isinstance(val, dict):
            token = val.get("key")
            return token
        return val

    def get_mineru_token_meta(self) -> Dict[str, Any]:
        """Return { key: str, configured: bool }"""
        secrets = self.load_secrets()
        # Support both new key (mineru_token) and old key (translator_mineru_token)
        val = secrets.get("mineru_token", secrets.get("translator_mineru_token"))
        if isinstance(val, dict):
            result = {"key": val.get("key", ""), "configured": bool(val.get("configured", bool(val.get("key"))))}
            return result
        key = str(val) if val is not None else ""
        result = {"key": key, "configured": bool(key)}
        return result

    def get_mineru_local_token(self) -> Optional[str]:
        """
        Get MinerU Local token (for self-hosted MinerU instances)
        
        Returns:
            MinerU Local token, returns None if not exists
        """
        secrets = self.load_secrets()
        val = secrets.get("mineru_local_token")
        if isinstance(val, dict):
            token = val.get("key")
            return token
        return val

    def get_mineru_local_token_meta(self) -> Dict[str, Any]:
        """Return { key: str, configured: bool } for MinerU Local"""
        secrets = self.load_secrets()
        val = secrets.get("mineru_local_token")
        if isinstance(val, dict):
            result = {"key": val.get("key", ""), "configured": bool(val.get("configured", bool(val.get("key"))))}
            return result
        key = str(val) if val is not None else ""
        result = {"key": key, "configured": bool(key)}
        return result

    def get_docling_auth(self) -> Dict[str, Any]:
        """
        Get Docling remote authentication configuration
        Return structure: {"auth_type": "none|bearer|header", "token": str, "header_name": str, "header_value": str}
        """
        secrets = self.load_secrets()
        return secrets.get("docling_auth", {})
    
    
    # Default password is now managed by unified user storage
    # This method is deprecated
    
    # Session secret key is now managed by local.json
    # This method is deprecated
    
    # Redis password is now managed by local.json
    # This method is deprecated
    
    @staticmethod
    def _count_configured_api_keys(secrets: Dict[str, Any]) -> int:
        """Count non-empty API keys / tokens in a secrets dict."""
        count = 0
        for key_name in ("api_keys", "platform_api_keys"):
            raw = secrets.get(key_name)
            if not isinstance(raw, dict):
                continue
            for _platform, val in raw.items():
                if isinstance(val, dict):
                    if str(val.get("key") or "").strip():
                        count += 1
                elif isinstance(val, str) and val.strip():
                    count += 1
        for token_key in ("mineru_token", "translator_mineru_token", "mineru_local_token"):
            val = secrets.get(token_key)
            if isinstance(val, dict) and str(val.get("key") or "").strip():
                count += 1
            elif isinstance(val, str) and val.strip():
                count += 1
        return count

    @staticmethod
    def _api_keys_map(secrets: Dict[str, Any]) -> Dict[str, Any]:
        raw = secrets.get("api_keys", secrets.get("platform_api_keys", {}))
        return raw if isinstance(raw, dict) else {}

    def save_secrets(self, secrets: Dict[str, Any]) -> bool:
        """
        Save sensitive configuration to file
        
        Args:
            secrets: Sensitive configuration to save
            
        Returns:
            Whether save was successful
        """
        try:
            # Refuse write after a failed load when the on-disk file still exists.
            # Empty in-memory state would otherwise wipe all API keys.
            if self._load_failed and self.secrets_file.exists():
                logger.error(
                    LogModule.CONFIG,
                    f"Refusing to save secrets.json: previous load failed "
                    f"({self._load_failed_reason!r}) and file exists at "
                    f"{self.secrets_file}",
                )
                return False

            incoming_keys = self._count_configured_api_keys(secrets or {})
            incoming_map = self._api_keys_map(secrets or {})
            if self.secrets_file.exists():
                try:
                    with open(self.secrets_file, "r", encoding="utf-8-sig") as fh:
                        on_disk = json.load(fh)
                    disk_dict = on_disk if isinstance(on_disk, dict) else {}
                    disk_keys = self._count_configured_api_keys(disk_dict)
                    disk_map = self._api_keys_map(disk_dict)
                except Exception as read_err:
                    logger.error(
                        LogModule.CONFIG,
                        f"Refusing to save secrets.json: cannot read existing "
                        f"file for wipe-guard ({read_err})",
                    )
                    return False
                # Only refuse wholesale wipe of the api_keys map itself.
                # Clearing individual keys (including optional-key local platforms)
                # is allowed when the map still has entries.
                if disk_keys > 0 and len(disk_map) > 0 and len(incoming_map) == 0:
                    logger.error(
                        LogModule.CONFIG,
                        f"Refusing to save secrets.json: would wipe "
                        f"{disk_keys} configured key(s) with empty api_keys map "
                        f"(path={self.secrets_file})",
                    )
                    return False
                if disk_keys > 0 and incoming_keys < disk_keys:
                    logger.warning(
                        LogModule.CONFIG,
                        f"Saving secrets.json with fewer configured keys: "
                        f"disk={disk_keys} incoming={incoming_keys} "
                        f"path={self.secrets_file}",
                    )

            # Ensure directory exists
            self.secrets_file.parent.mkdir(parents=True, exist_ok=True)

            # Backup existing file before overwrite
            if self.secrets_file.exists():
                try:
                    backup_path = self.secrets_file.with_suffix(".json.bak")
                    import shutil
                    shutil.copy2(self.secrets_file, backup_path)
                except Exception as bak_err:
                    logger.warning(
                        LogModule.CONFIG,
                        f"Failed to write secrets.json.bak: {bak_err}",
                    )

            # Atomic write
            import tempfile
            fd, tmp_path = tempfile.mkstemp(
                prefix=".secrets_",
                suffix=".tmp",
                dir=str(self.secrets_file.parent),
            )
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(secrets, f, indent=2, ensure_ascii=False)
                os.replace(tmp_path, self.secrets_file)
            except Exception:
                try:
                    if os.path.exists(tmp_path):
                        os.unlink(tmp_path)
                except OSError:
                    pass
                raise
            
            # Update cache
            self._secrets_cache = secrets
            self._load_failed = False
            self._load_failed_reason = None
            
            logger.info(
                LogModule.CONFIG,
                f"Sensitive configuration saved to: {self.secrets_file} "
                f"(configured_keys={incoming_keys})",
            )
            return True
            
        except Exception as e:
            logger.error(LogModule.CONFIG, f"Failed to save sensitive configuration file: {e}")
            return False
    
    def _platform_allows_empty_api_key(self, platform: str) -> bool:
        """Return True when platform config says API key is optional (local deploys)."""
        try:
            from backend.config.platforms_config import get_platforms_config

            cfg = get_platforms_config().get_platform_config(platform)
            if cfg is None:
                return False
            return not bool(getattr(cfg, "requires_api_key", True))
        except Exception as exc:
            logger.debug(
                LogModule.CONFIG,
                f"Could not resolve requires_api_key for '{platform}': {exc}",
            )
            return False

    def update_platform_api_key(
        self,
        platform: str,
        api_key: str,
        configured: Optional[bool] = None,
        *,
        allow_clear: Optional[bool] = None,
    ) -> bool:
        """
        Update API key for specified platform
        
        Args:
            platform: Platform name
            api_key: API key
            configured: Whether the key is configured (auto-detect if None)
            allow_clear: If True, allow empty key to clear/store empty.
                If None, auto-allow when platform.requires_api_key is False
                (local deployments that do not need a key).
            
        Returns:
            Whether update was successful
        """
        api_key_str = "" if api_key is None else str(api_key)
        if allow_clear is None:
            allow_clear = self._platform_allows_empty_api_key(platform)
        if not api_key_str.strip() and not allow_clear:
            # Match single-setting API: only persist non-empty keys by default
            existing = self.get_api_key(platform)
            if existing:
                logger.warning(
                    LogModule.CONFIG,
                    f"Skipping empty API key update for platform '{platform}' "
                    f"(existing key present; platform requires_api_key)",
                )
                return True
            logger.info(
                LogModule.CONFIG,
                f"Skipping empty API key update for platform '{platform}' "
                f"(nothing to write)",
            )
            return True

        secrets = self.load_secrets()
        if self._load_failed:
            logger.error(
                LogModule.CONFIG,
                f"Cannot update API key for '{platform}': secrets load failed",
            )
            return False
        # Use new key "api_keys" if available, otherwise fall back to "platform_api_keys"
        api_keys_key = "api_keys" if "api_keys" in secrets else "platform_api_keys"
        if api_keys_key not in secrets:
            secrets[api_keys_key] = {}
        key_meta = secrets[api_keys_key].get(platform)
        if not isinstance(key_meta, dict):
            key_meta = {"key": "", "configured": False}
        key_meta["key"] = api_key_str
        if configured is None:
            # Optional-key platforms: empty key still counts as configured for local use
            if allow_clear and not api_key_str.strip():
                key_meta["configured"] = True
            else:
                key_meta["configured"] = bool(api_key_str)
        else:
            key_meta["configured"] = bool(configured)
        secrets[api_keys_key][platform] = key_meta
        # Also update old key for backward compatibility if it exists
        if "platform_api_keys" in secrets and api_keys_key != "platform_api_keys":
            secrets["platform_api_keys"][platform] = key_meta
        logger.info(
            LogModule.CONFIG,
            f"Updating API key for '{platform}' "
            f"(empty={not bool(api_key_str.strip())}, allow_clear={allow_clear})",
        )
        return self.save_secrets(secrets)
    
    def update_api_key(self, platform: str, api_key: str, configured: Optional[bool] = None) -> bool:
        """
        Update API key for any platform (AI platforms or MinerU)
        
        Args:
            platform: Platform name
            api_key: API key
            configured: Whether the key is configured (auto-detect if None)
            
        Returns:
            Whether update was successful
        """
        if platform == "mineru":
            return self.update_mineru_token(api_key, configured)
        elif platform == "mineru_local":
            return self.update_mineru_local_token(api_key, configured)
        else:
            return self.update_platform_api_key(platform, api_key, configured)
    
    def update_mineru_token(self, token: str, configured: Optional[bool] = None) -> bool:
        """
        Update MinerU token
        
        Args:
            token: MinerU token
            
        Returns:
            Whether update was successful
        """
        secrets = self.load_secrets()
        # Use new key "mineru_token" if available, otherwise fall back to "translator_mineru_token"
        mineru_key = "mineru_token" if "mineru_token" in secrets else "translator_mineru_token"
        meta = secrets.get(mineru_key)
        if not isinstance(meta, dict):
            meta = {"key": "", "configured": False}
        meta["key"] = token
        meta["configured"] = bool(configured) if configured is not None else bool(token)
        secrets[mineru_key] = meta
        # Also update old key for backward compatibility if it exists
        if "translator_mineru_token" in secrets and mineru_key != "translator_mineru_token":
            secrets["translator_mineru_token"] = meta
        result = self.save_secrets(secrets)
        return result
    
    def update_mineru_local_token(self, token: str, configured: Optional[bool] = None) -> bool:
        """
        Update MinerU Local token (for self-hosted MinerU instances)
        
        Args:
            token: MinerU Local token
            configured: Whether the token is configured (auto-detect if None)
            
        Returns:
            Whether update was successful
        """
        secrets = self.load_secrets()
        meta = secrets.get("mineru_local_token")
        if not isinstance(meta, dict):
            meta = {"key": "", "configured": False}
        meta["key"] = token
        meta["configured"] = bool(configured) if configured is not None else bool(token)
        secrets["mineru_local_token"] = meta
        result = self.save_secrets(secrets)
        return result

    # ==== Web/HTTPS TLS Private Key Password ====
    def get_web_tls_password(self) -> Optional[str]:
        secrets = self.load_secrets()
        return secrets.get("web_tls", {}).get("key_password")

    def update_web_tls_password(self, password: Optional[str]) -> bool:
        secrets = self.load_secrets()
        if "web_tls" not in secrets:
            secrets["web_tls"] = {}
        if password:
            secrets["web_tls"]["key_password"] = password
        else:
            # Remove key when clearing to avoid residue
            secrets["web_tls"].pop("key_password", None)
        return self.save_secrets(secrets)
    
    def has_secrets_file(self) -> bool:
        """
        Check if sensitive configuration file exists
        
        Returns:
            Whether file exists
        """
        return self.secrets_file.exists()
    
    def create_template_file(self) -> bool:
        """
        Create configuration template file
        
        Returns:
            Whether creation was successful
        """
        template_file = self.secrets_file.parent / f"{self.secrets_file.stem}.template"
        
        template_content = {
            "_comment": "Sensitive configuration file template - please copy as secrets.json and fill in real values",
            "_warning": "This file contains sensitive information, do not commit to git repository",
            "_note": "Leave API key as empty string \"\" if not configured",
            
            "platform_api_keys": {
                "openai": "",
                "azure": "", 
                "anthropic": "",
                "google": "",
                "mistral": "",
                "cohere": "",
                "xai": "",
                "groq": "",
                "together": "",
                "deepseek": "",
                "dashscope": "",
                "volcengine_ark": "",
                "siliconflow": "",
                "zhipu": "",
                "dmxapi": "",
                "local": ""
            },
            
            "translator_mineru_token": "",
            
        }
        
        try:
            with open(template_file, 'w', encoding='utf-8') as f:
                json.dump(template_content, f, indent=2, ensure_ascii=False)
            
            logger.info(LogModule.CONFIG, f"Configuration template file created: {template_file}")
            return True
        except Exception as e:
            logger.error(LogModule.CONFIG, f"Failed to create configuration template file: {e}")
            return False

    def update_docling_auth(self, auth: Dict[str, Any]) -> bool:
        """Update Docling remote authentication configuration"""
        secrets = self.load_secrets()
        secrets["docling_auth"] = {
            "auth_type": auth.get("auth_type", "none"),
            "token": auth.get("token", ""),
            "header_name": auth.get("header_name", ""),
            "header_value": auth.get("header_value", ""),
        }
        self.save_secrets(secrets)
        logger.info(LogModule.CONFIG, "Docling auth secrets updated")
        return True

    def get_donor_activation(self) -> Dict[str, Any]:
        """
        Get donor activation status.

        Returns:
            Dictionary with 'activated', 'license_token', 'trial_start_date' (ISO date or None).
            Does not expose plaintext activation codes.
        """
        secrets = self.load_secrets()
        obf = secrets.get("__da")
        activated = False
        license_token = None
        trial_start_date = None

        if isinstance(obf, dict):
            try:
                activated = bool(obf.get("f", False))
                license_token = obf.get("t")
                trial_start_date = self._decode_trial_date_obfuscated(obf.get("s"))
            except Exception:
                activated = False
                license_token = None
                trial_start_date = None

        # Fallback to legacy clear-text structure if obfuscated data not available
        if trial_start_date is None:
            legacy = secrets.get("donor_activation", {})
            if isinstance(legacy, dict):
                activated = bool(legacy.get("activated", activated))
                license_token = legacy.get("license_token", license_token)
                ts = legacy.get("trial_start_date")
                if isinstance(ts, str) and ts:
                    trial_start_date = ts

        # Use effective trial start (earliest of secrets and trial anchor) to harden against reinstall reset
        try:
            from utils.donor_trial import get_effective_trial_start
            trial_start_date = get_effective_trial_start(trial_start_date)
        except Exception:
            pass

        return {
            "activated": activated,
            "license_token": license_token,
            "trial_start_date": trial_start_date,
        }

    def update_donor_activation(self, activated: bool, license_token: Optional[str] = None) -> bool:
        """
        Update donor activation status.

        Args:
            activated: Whether donor is activated.
            license_token: Signed registration code (optional); never store plaintext codes.

        Returns:
            Whether update was successful.
        """
        secrets = self.load_secrets()
        obf = secrets.get("__da")
        # Preserve existing trial_start_date when updating activation
        existing_plain: Optional[str] = None
        if isinstance(obf, dict):
            existing_plain = self._decode_trial_date_obfuscated(obf.get("s"))
        if not existing_plain:
            # Fallback to legacy clear-text trial_start_date if present
            legacy = secrets.get("donor_activation", {})
            if isinstance(legacy, dict):
                ts = legacy.get("trial_start_date")
                if isinstance(ts, str) and ts:
                    existing_plain = ts
        if not existing_plain:
            existing_plain = date.today().isoformat()

        secrets["__da"] = {
            "f": bool(activated),
            "t": license_token if license_token is not None else (obf.get("t") if isinstance(obf, dict) else None),
            "s": self._encode_trial_date_obfuscated(existing_plain),
        }
        # Remove legacy clear-text donor_activation block
        if "donor_activation" in secrets:
            del secrets["donor_activation"]

        result = self.save_secrets(secrets)
        if result:
            logger.info(LogModule.CONFIG, f"Donor activation updated: activated={activated}")
        return result


# Global instance
_secrets_manager: Optional[SecretsManager] = None
_secrets_manager_loading: bool = False  # Flag to prevent concurrent loading


def get_secrets_manager() -> SecretsManager:
    """Get global sensitive configuration manager instance with caching to avoid duplicate loading"""
    global _secrets_manager, _secrets_manager_loading
    if _secrets_manager is None and not _secrets_manager_loading:
        _secrets_manager_loading = True
        try:
            _secrets_manager = SecretsManager()
        finally:
            _secrets_manager_loading = False
    return _secrets_manager
