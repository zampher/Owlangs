#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Owlangs first deployment setup script
Automatically complete basic configuration required for first deployment
"""

import os
import shutil
import json
import secrets
import string
from pathlib import Path


def generate_random_key(length=32):
    """Generate random key"""
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def setup_first_deploy():
    """First deployment setup"""
    print("🚀 Owlangs first deployment setup")
    print("=" * 50)
    
    # 1. Create secrets.json (new config system)
    # SecretsManager will automatically create from template if needed
    from utils.path_utils import get_config_file_path, get_template_file_path
    
    secrets_path = get_config_file_path("secrets.json")
    secrets_template_path = get_template_file_path("secrets.json.template")
    
    if not secrets_path.exists() and secrets_template_path.exists():
        try:
            secrets_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(secrets_template_path, secrets_path)
            # Set conservative permissions: rw-r----- (0640)
            try:
                os.chmod(secrets_path, 0o640)
            except Exception:
                pass
            print("✅ Created secrets.json configuration file from template")
        except Exception as e:
            print(f"❌ Failed to create secrets.json: {e}")
    elif secrets_path.exists():
        print("ℹ️  secrets.json already exists, skipping creation")
    else:
        print("⚠️  secrets.json.template not found, secrets.json will be created automatically when needed")
    
    # 2. Check and create necessary directories
    directories = ['logs', 'output', 'certs', 'glossaries', 'user_profiles']
    for directory in directories:
        if not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)
            print(f"✅ Created directory: {directory}")
    
    # 3. Check configuration files (new config structure)
    config_files = {
        'system.json': 'System configuration',
        'platforms.json': 'Platforms configuration',
        'ui.json': 'UI configuration',
        'secrets.json': 'Secrets configuration',
        'local.json': 'Local configuration',
        'app_config.json': 'Application configuration'
    }
    for config_file, description in config_files.items():
        config_path = get_config_file_path(config_file)
        if config_path.exists():
            print(f"✅ {description} exists: {config_file}")
        else:
            print(f"⚠️  {description} missing: {config_file} (will be created from template if available)")
    
    # 4. Display next steps guide
    print("\n" + "=" * 50)
    print("🎉 First deployment setup completed!")
    print("\n📋 Next steps:")
    print("1. Edit secrets.json file to set your API keys")
    print("2. Install Redis service (for session management)")
    print("3. Start Owlangs service")
    print("\n🔧 Startup command:")
    print("   .venv\\Scripts\\python.exe -m backend.cli -i")
    print("\n🌐 Access URL:")
    print("   http://127.0.0.1:8800")
    print("\n👤 Default login information:")
    print("   Username: admin")
    print("   Password: [Set via unified user storage]")
    print("\n📚 For more information, check the documents in the doc/ directory")


if __name__ == "__main__":
    setup_first_deploy()
