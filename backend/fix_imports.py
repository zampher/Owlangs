#!/usr/bin/env python3
"""
批量修复导入路径的脚本
"""

import os
import re
from pathlib import Path

def fix_imports_in_file(file_path):
    """修复单个文件中的导入"""
    try:
        with open(file_path, 'r', encoding='utf-8-sig') as f:
            content = f.read()
        
        original_content = content
        
        # 修复各种导入模式
        patterns = [
            # from xxx import yyy
            (r'from backend\.([^ ]+) import', r'from \1 import'),
            # import xxx
            (r'import backend\.([^ ]+)', r'import \1'),
        ]
        
        for pattern, replacement in patterns:
            content = re.sub(pattern, replacement, content)
        
        # 如果内容有变化，写回文件
        if content != original_content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"✅ Fixed: {file_path}")
            return True
        else:
            print(f"⏭️  No changes: {file_path}")
            return False
            
    except Exception as e:
        print(f"❌ Error fixing {file_path}: {e}")
        return False

def main():
    """主函数"""
    print("🔧 Fixing import paths...")
    
    # 获取所有Python文件
    python_files = []
    for root, dirs, files in os.walk('.'):
        for file in files:
            if file.endswith('.py'):
                python_files.append(os.path.join(root, file))
    
    print(f"Found {len(python_files)} Python files")
    
    fixed_count = 0
    for file_path in python_files:
        if fix_imports_in_file(file_path):
            fixed_count += 1
    
    print(f"\n✅ Fixed {fixed_count} files")

if __name__ == "__main__":
    main()


