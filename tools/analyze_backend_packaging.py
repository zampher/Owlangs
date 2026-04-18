#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
分析 backend 目录结构和 .spec 文件，检查打包时是否遗漏了必要的 Python 模块
"""

import os
import glob
import re
from pathlib import Path

def list_backend_files():
    """列出 backend 目录下所有文件路径和文件名"""
    backend_dir = Path("backend")
    files = []

    for root, dirs, filenames in os.walk(backend_dir):
        for filename in filenames:
            if filename.endswith('.py') and 'test' not in root.lower() and 'tests' not in root.lower():
                file_path = Path(root) / filename
                files.append({
                    'path': str(file_path),
                    'name': filename,
                    'relative_path': str(file_path.relative_to(backend_dir))
                })

    return files

def find_spec_files():
    """查找所有的 .spec 文件"""
    spec_files = glob.glob('*.spec')
    return spec_files

def analyze_spec_file(spec_file):
    """分析单个 .spec 文件的内容"""
    with open(spec_file, 'r', encoding='utf-8') as f:
        content = f.read()

    # 查找 hiddenimports
    hiddenimports = re.findall(r'hiddenimports\s*=\s*\[([^\]]+)\]', content)
    if hiddenimports:
        hiddenimports = re.findall(r"'([^']+)'", hiddenimports[0])

    # 查找 excludes
    excludes = re.findall(r'excludes\s*=\s*\[([^\]]+)\]', content)
    if excludes:
        excludes = re.findall(r"'([^']+)'", excludes[0])

    # 查找 includes
    includes = re.findall(r'includes\s*=\s*\[([^\]]+)\]', content)
    if includes:
        includes = re.findall(r"'([^']+)'", includes[0])

    return {
        'file': spec_file,
        'hiddenimports': hiddenimports,
        'excludes': excludes,
        'includes': includes
    }

def check_missing_modules(backend_files, spec_analysis):
    """检查是否有遗漏的模块"""
    missing_modules = []

    # 获取所有 backend 文件的基本名称（不带 .py）
    backend_modules = set()
    for file in backend_files:
        module_path = file['relative_path'].replace('/', '.').replace('\\', '.').replace('.py', '')
        backend_modules.add(module_path)

    # 检查 hiddenimports 是否在 backend 文件中存在
    for hiddenimport in spec_analysis.get('hiddenimports', []):
        if hiddenimport not in backend_modules:
            missing_modules.append(f"hiddenimport '{hiddenimport}' not found in backend files")

    # 检查 includes 是否在 backend 文件中存在
    for include in spec_analysis.get('includes', []):
        if include not in backend_modules:
            missing_modules.append(f"include '{include}' not found in backend files")

    return missing_modules

def main():
    print("=== Backend 文件分析 ===")
    print()

    # 列出 backend 文件
    backend_files = list_backend_files()
    print(f"找到 {len(backend_files)} 个 backend Python 文件（排除 test 目录）:")
    for file in backend_files:
        print(f"  - {file['relative_path']}")
    print()

    # 查找 .spec 文件
    spec_files = find_spec_files()
    print(f"找到 {len(spec_files)} 个 .spec 文件:")
    for spec_file in spec_files:
        print(f"  - {spec_file}")
    print()

    # 分析每个 .spec 文件
    for spec_file in spec_files:
        print(f"=== 分析 {spec_file} ===")
        analysis = analyze_spec_file(spec_file)

        print("  Hidden Imports:")
        if analysis['hiddenimports']:
            for imp in analysis['hiddenimports']:
                print(f"    - {imp}")
        else:
            print("    - 无")

        print("  Includes:")
        if analysis['includes']:
            for inc in analysis['includes']:
                print(f"    - {inc}")
        else:
            print("    - 无")

        print("  Excludes:")
        if analysis['excludes']:
            for exc in analysis['excludes']:
                print(f"    - {exc}")
        else:
            print("    - 无")

        # 检查缺失的模块
        missing = check_missing_modules(backend_files, analysis)
        if missing:
            print("  WARNING: 发现潜在问题:")
            for issue in missing:
                print(f"    - {issue}")
        else:
            print("  OK: 没有发现明显问题")

        print()

if __name__ == "__main__":
    main()