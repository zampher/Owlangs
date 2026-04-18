#!/usr/bin/env python3
"""
Initialize local user data
Initialize local user data
"""

import json
import os
import sys
import hashlib
import hmac
import time
from datetime import datetime

def hash_password(password: str, salt: str = None) -> str:
    """Hash password"""
    if salt is None:
        salt = os.urandom(32).hex()
    
    # Use HMAC-SHA256 for password hashing
    password_hash = hmac.new(
        salt.encode('utf-8'),
        password.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    return f"{salt}:{password_hash}"

def initialize_local_users():
    """Initialize local user data"""
    template_file = "local_users.json.template"
    output_file = "local_users.json"
    
    if not os.path.exists(template_file):
        print(f"❌ Template file does not exist: {template_file}")
        return False
    
    # Read template
    with open(template_file, 'r', encoding='utf-8-sig') as f:
        template_data = json.load(f)
    
    # Generate timestamp
    timestamp = datetime.now().isoformat()
    
    # Process user data
    for user in template_data["users"]:
        username = user["username"]
        
        # Get default password from environment or prompt user
        if username == "admin":
            default_password = os.getenv("ADMIN_DEFAULT_PASSWORD")
            if not default_password:
                default_password = input(f"Enter password for {username}: ").strip()
                if not default_password:
                    print(f"❌ Password for {username} is required!")
                    return False
        else:
            default_password = template_data["metadata"]["default_passwords"].get(username, "password123")
        
        # Generate password hash
        password_hash = hash_password(default_password)
        
        # Replace template variables
        user["password_hash"] = password_hash
        user["created_at"] = timestamp
    
    # Update metadata
    template_data["metadata"]["created_at"] = timestamp
    
    # Write to output file
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(template_data, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Local user data initialization completed: {output_file}")
    print("📋 Default user accounts:")
    for username, password in template_data["metadata"]["default_passwords"].items():
        print(f"  - Username: {username}, Password: {password}")
    
    return True

if __name__ == "__main__":
    if initialize_local_users():
        print("🎉 Initialization successful!")
        sys.exit(0)
    else:
        print("❌ Initialization failed!")
        sys.exit(1)
