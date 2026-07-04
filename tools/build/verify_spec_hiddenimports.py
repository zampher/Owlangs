#!/usr/bin/env python3
"""
验证spec文件中的hiddenimports是否能够正确导入
用于检查PyInstaller打包配置是否完整
"""
import sys
import importlib
from pathlib import Path

def check_hiddenimports(spec_file):
    """检查spec文件中定义的hiddenimports是否都能导入"""
    spec_path = Path(spec_file)
    if not spec_path.exists():
        print(f"❌ Spec文件不存在: {spec_file}")
        return False

    # 读取spec文件并提取hiddenimports
    print(f"\n📋 检查spec文件: {spec_file}")
    print("=" * 60)

    spec_content = spec_path.read_text()

    # 提取hiddenimports列表（简单解析，不执行spec代码）
    hiddenimports = []
    in_list = False
    for line in spec_content.split('\n'):
        if 'hiddenimports = [' in line:
            in_list = True
            continue
        if in_list and line.strip() == ']':
            in_list = False
            break
        if in_list:
            # 提取模块名（去除注释和引号）
            line = line.strip()
            if line.startswith("'") or line.startswith('"'):
                module_name = line.split("'")[1] if "'" in line else line.split('"')[1]
                # 去除注释
                if '#' in module_name:
                    module_name = module_name.split('#')[0].strip()
                hiddenimports.append(module_name)

    print(f"📦 找到 {len(hiddenimports)} 个hiddenimports模块")

    # 添加backend到sys.path（模拟PyInstaller的pathex）
    backend_path = Path(__file__).parent.parent / 'backend'
    if backend_path.exists():
        sys.path.insert(0, str(backend_path))
        print(f"✅ 添加backend路径: {backend_path}")

    # 添加项目根目录到sys.path
    project_root = Path(__file__).parent.parent
    if project_root.exists():
        sys.path.insert(0, str(project_root))
        print(f"✅ 添加项目根目录: {project_root}")

    # 检查每个模块
    failed = []
    success = []
    optional = []

    for module in hiddenimports:
        try:
            importlib.import_module(module)
            success.append(module)
            print(f"  ✅ {module}")
        except ImportError as e:
            # 检查是否是可选模块（第三方库）
            if module in ['mobi', 'ebooklib', 'loguru', 'pptx', 'html2text', 'bs4',
                          'pygments', 'latex2mathml', 'mathml2omml', 'mathml2omml_as',
                          'json_repair', 'imghdr']:
                optional.append((module, str(e)))
                print(f"  ⚠️  {module} (可选第三方库，未安装)")
            else:
                failed.append((module, str(e)))
                print(f"  ❌ {module} - {e}")

    # 总结
    print("\n" + "=" * 60)
    print(f"📊 结果统计:")
    print(f"  ✅ 成功导入: {len(success)}")
    print(f"  ⚠️  可选库未安装: {len(optional)}")
    print(f"  ❌ 导入失败: {len(failed)}")

    if failed:
        print("\n❌ 以下模块导入失败（需要处理）:")
        for module, error in failed:
            print(f"  - {module}: {error}")
        return False
    else:
        print("\n✅ 所有必需模块都能正确导入!")
        if optional:
            print("\n⚠️  注意: 以下可选第三方库未安装（打包时需要）:")
            for module, _ in optional:
                print(f"  - {module}")
        return True

def main():
    """主函数"""
    project_root = Path(__file__).parent.parent

    spec_files = [
        project_root / 'lite.spec',
        project_root / 'launcher_portable_onedir.spec',
        project_root / 'macos.spec',
    ]

    print("🔍 Owlangs Spec文件验证工具")
    print("=" * 60)

    all_passed = True
    for spec_file in spec_files:
        if spec_file.exists():
            if not check_hiddenimports(spec_file):
                all_passed = False

    print("\n" + "=" * 60)
    if all_passed:
        print("✅ 所有spec文件验证通过!")
        print("\n建议:")
        print("  1. 运行PyInstaller构建测试: pyinstaller -y --clean lite.spec")
        print("  2. 测试构建产物是否能正常导入MOBI/EPUB文件")
    else:
        print("❌ 验证失败，请检查上述错误并修复")
        print("\n可能的解决方案:")
        print("  1. 检查模块路径是否正确")
        print("  2. 安装缺失的第三方库")
        print("  3. 检查backend目录结构是否完整")

    return 0 if all_passed else 1

if __name__ == '__main__':
    sys.exit(main())