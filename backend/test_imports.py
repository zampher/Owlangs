#!/usr/bin/env python3
"""
测试导入是否正常工作
"""

import sys
import os

# 添加当前目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    print("Testing imports...")
    
    # 测试基本导入
    from backend import __version__
    print(f"✅ __version__: {__version__}")
    
    from app.utils.app_utils import run_app
    print("✅ app.utils.app_utils imported")
    
    from app.factory import create_app
    print("✅ app.factory imported")
    
    print("✅ All imports successful!")
    
except ImportError as e:
    print(f"❌ Import error: {e}")
    import traceback
    traceback.print_exc()
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()


