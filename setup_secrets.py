#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Sensitive configuration initialization script
Used to set API keys and other sensitive information during first deployment
"""

import json
import os
import sys
from pathlib import Path

def main():
    """Main function"""
    print("🔐 Owlangs sensitive configuration initialization")
    print("=" * 50)
    
    # Check if sensitive configuration file already exists
    secrets_file = Path("secrets.json")
    if secrets_file.exists():
        print(f"⚠️  Sensitive configuration file {secrets_file} already exists")
        response = input("Do you want to reconfigure? (y/N): ").strip().lower()
        if response != 'y':
            print("Configuration cancelled")
            return
    
    # Create configuration template
    template_file = Path("secrets.json.template")
    if not template_file.exists():
        print(f"❌ Template file {template_file} does not exist")
        return
    
    print("\n📋 Please configure the following sensitive information (press Enter to skip):")
    print("=" * 50)
    
    # Read template
    with open(template_file, 'r', encoding='utf-8-sig') as f:
        secrets = json.load(f)
    
    # Configure API keys (supports new structure { key, configured } and compatible with old string structure)
    print("\n🔑 API key configuration:")
    api_keys = secrets.get("platform_api_keys", {})
    for platform, placeholder in list(api_keys.items()):
        # Normalize to object structure
        if isinstance(placeholder, str):
            placeholder_obj = {"key": placeholder, "configured": bool(placeholder and not placeholder.startswith("your-"))}
            api_keys[platform] = placeholder_obj
        else:
            placeholder_obj = placeholder or {"key": "", "configured": False}

        key_placeholder = placeholder_obj.get("key") or ""
        # Only prompt for input when it's a template placeholder
        if isinstance(key_placeholder, str) and key_placeholder.startswith("your-"):
            current_value = input(f"  {platform}: ").strip()
            if current_value:
                api_keys[platform]["key"] = current_value
                api_keys[platform]["configured"] = True
            else:
                # Keep unconfigured
                api_keys[platform]["key"] = ""
                api_keys[platform]["configured"] = False
    
    # Configure MinerU token (supports new structure { key, configured } and compatible with old string structure)
    print("\n🔧 MinerU token configuration:")
    mineru_entry = secrets.get("translator_mineru_token")
    if isinstance(mineru_entry, dict):
        current_placeholder = mineru_entry.get("key") or ""
    else:
        current_placeholder = mineru_entry or ""

    mineru_token = input("  MinerU Token: ").strip()
    if isinstance(mineru_entry, dict):
        secrets["translator_mineru_token"]["key"] = mineru_token if mineru_token else ""
        secrets["translator_mineru_token"]["configured"] = bool(mineru_token)
    else:
        # Fallback: use new structure
        secrets["translator_mineru_token"] = {"key": mineru_token if mineru_token else "", "configured": bool(mineru_token)}
    
    # Authentication is now managed by unified user storage and local.json
    print("\n🔐 Authentication configuration:")
    print("  ✅ Admin password: Managed by unified user storage")
    print("  ✅ Session key: Managed by local.json")
    print("  ✅ Redis password: Managed by local.json")
    
    # Save configuration
    try:
        with open(secrets_file, 'w', encoding='utf-8') as f:
            json.dump(secrets, f, indent=2, ensure_ascii=False)
        
        print(f"\n✅ Sensitive configuration saved to: {secrets_file}")
        print("🔒 This file contains sensitive information, do not commit to git repository")
        
        # Set file permissions (owner read/write only)
        os.chmod(secrets_file, 0o600)
        print("🔐 File permissions set to owner read/write only")
        
    except Exception as e:
        print(f"❌ Failed to save configuration: {e}")
        return
    
    print("\n📝 Configuration summary:")
    print("=" * 50)
    
    # Count configured API keys (adapted to new structure)
    configured_keys = 0
    total_keys = len(api_keys)
    for val in api_keys.values():
        if isinstance(val, dict):
            if val.get("configured") and (val.get("key") or "").strip():
                configured_keys += 1
        else:
            if val and str(val).strip():
                configured_keys += 1
    print(f"  API keys: {configured_keys}/{total_keys} configured")
    
    # Display other configuration status
    mt = secrets.get('translator_mineru_token')
    if isinstance(mt, dict):
        mineru_configured = bool(mt.get('configured') and (mt.get('key') or '').strip())
    else:
        mineru_configured = bool(mt and str(mt).strip())
    print(f"  MinerU token: {'configured' if mineru_configured else 'not configured'}")
    print(f"  Default password: Managed by unified user storage")
    print(f"  Session key: Managed by local.json")
    print(f"  Redis password: Managed by local.json")
    
    print("\n🚀 Configuration completed! You can now start the Owlangs service")
    print("💡 Tip: After admin login, you can continue configuring API keys in the web interface")

if __name__ == "__main__":
    main()
