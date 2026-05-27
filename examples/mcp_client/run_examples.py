#!/usr/bin/env python3
"""MCP Client Example 测试运行器

自动运行 examples/mcp_client 目录下的所有 example 脚本，
使用 test/ 目录下的测试数据进行端到端验证。

用法:
    cd <project_root>
    python examples/mcp_client/run_examples.py [选项]

选项:
    --host HOST        MCP server 地址 (默认: 127.0.0.1)
    --port PORT        MCP server 端口 (默认: 8100)
    --parallel         并行运行所有测试（默认串行，并发限制为2）
    --timeout <秒>     单个测试超时时间（默认 7200 秒 = 2 小时）
    --filter <关键词>   只运行名称包含关键词的测试
    --list             只列出测试用例，不执行
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass
from typing import Optional

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

PYTHON = sys.executable
SCRIPT_DIR = ROOT / "examples" / "mcp_client"
TEST_DATA_DIR = ROOT / "test"

# ── 测试用例定义 ──
# 注意: example_download_batch.py 需要已知 task_id，不在自动化测试列表中
TEST_CASES = [
    {
        "name": "translate_single_pdf",
        "script": "examples/mcp_client/example_translate_single.py",
        "args": ["test/6_PDFsam_尿素吸附.pdf", "Chinese"],
        "desc": "单文件翻译：中文PDF -> Chinese",
    },
    {
        "name": "convert_single_pdf",
        "script": "examples/mcp_client/example_convert_single.py",
        "args": ["test/6_PDFsam_尿素吸附.pdf"],
        "desc": "单文件格式转换：中文PDF",
    },
    {
        "name": "translate_single_excel",
        "script": "examples/mcp_client/example_translate_single.py",
        "args": ["test/booklist2.xlsx", "Chinese"],
        "desc": "单文件翻译：Excel -> Chinese",
    },
    {
        "name": "translate_single_md",
        "script": "examples/mcp_client/example_translate_single.py",
        "args": ["test/test_mcp_translate.md", "Chinese"],
        "desc": "单文件翻译：Markdown -> Chinese",
    },
    {
        "name": "translate_zip",
        "script": "examples/mcp_client/example_translate_zip.py",
        "args": ["test/test2.zip", "Chinese"],
        "desc": "ZIP批量翻译 -> Chinese",
    },
]

# 返回码含义映射
EXIT_CODES = {
    0: "成功",
    1: "参数错误 / 文件不存在 / 提交失败 / 无任务完成",
    2: "任务执行失败或被取消",
}


@dataclass
class TestResult:
    name: str
    desc: str
    script: str
    args: list
    returncode: int = -1
    stdout: str = ""
    stderr: str = ""
    elapsed: float = 0.0
    status: str = "pending"
    error_msg: str = ""


def parse_args():
    """解析命令行参数。"""
    parallel = "--parallel" in sys.argv
    list_only = "--list" in sys.argv
    timeout = 7200
    filter_kw = None
    host = "127.0.0.1"
    port = 8100

    if "--timeout" in sys.argv:
        idx = sys.argv.index("--timeout")
        if idx + 1 < len(sys.argv):
            timeout = int(sys.argv[idx + 1])

    if "--filter" in sys.argv:
        idx = sys.argv.index("--filter")
        if idx + 1 < len(sys.argv):
            filter_kw = sys.argv[idx + 1].lower()

    if "--host" in sys.argv:
        idx = sys.argv.index("--host")
        if idx + 1 < len(sys.argv):
            host = sys.argv[idx + 1]

    if "--port" in sys.argv:
        idx = sys.argv.index("--port")
        if idx + 1 < len(sys.argv):
            port = int(sys.argv[idx + 1])

    return host, port, parallel, list_only, timeout, filter_kw


def check_prerequisites():
    """检查运行环境是否满足要求。"""
    issues = []

    # 检查 example 脚本
    for tc in TEST_CASES:
        script_path = ROOT / tc["script"]
        if not script_path.exists():
            issues.append(f"测试脚本缺失: {script_path}")

    # 检查共享模块
    if not (SCRIPT_DIR / "mcp_client.py").exists():
        issues.append(f"共享客户端模块缺失: {SCRIPT_DIR / 'mcp_client.py'}")

    # 检查测试数据
    test_files = [
        "test/6_PDFsam_尿素吸附.pdf",
        "test/booklist2.xlsx",
        "test/test_mcp_translate.md",
        "test/test2.zip",
    ]
    for f in test_files:
        path = ROOT / f
        if not path.exists():
            issues.append(f"测试数据缺失: {path}")

    return issues


async def run_single_test(
    tc: dict,
    host: str,
    port: int,
    timeout: int,
    semaphore: Optional[asyncio.Semaphore] = None,
) -> TestResult:
    """运行单个测试用例。"""
    result = TestResult(
        name=tc["name"],
        desc=tc["desc"],
        script=tc["script"],
        args=tc["args"],
    )

    if semaphore:
        async with semaphore:
            return await _do_run(result, host, port, timeout)
    else:
        return await _do_run(result, host, port, timeout)


async def _do_run(result: TestResult, host: str, port: int, timeout: int) -> TestResult:
    """执行实际子进程调用。"""
    script_path = ROOT / result.script
    cmd = [
        PYTHON, str(script_path),
        *result.args,
        "--host", host,
        "--port", str(port),
    ]

    result.status = "running"
    print(f"\n[START] {result.name}: {result.desc}")
    print(f"  CMD: {' '.join(cmd)}")

    start_time = datetime.now()

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(ROOT),
        )

        stdout, stderr = await asyncio.wait_for(
            proc.communicate(), timeout=timeout
        )

        result.returncode = proc.returncode
        result.stdout = stdout.decode("utf-8", errors="replace")
        result.stderr = stderr.decode("utf-8", errors="replace")

    except asyncio.TimeoutError:
        result.status = "timeout"
        result.error_msg = f"测试运行超过 {timeout} 秒超时"
        try:
            proc.kill()
            await proc.wait()
        except Exception:
            pass
        print(f"  [TIMEOUT] {result.name}")
        return result
    except Exception as e:
        result.status = "error"
        result.error_msg = str(e)
        print(f"  [ERROR] {result.name}: {e}")
        return result

    result.elapsed = (datetime.now() - start_time).total_seconds()

    if result.returncode == 0:
        result.status = "passed"
        print(f"  [PASSED] {result.name}  ({result.elapsed:.1f}s)")
    else:
        result.status = "failed"
        exit_desc = EXIT_CODES.get(result.returncode, f"未知返回码 {result.returncode}")
        result.error_msg = exit_desc
        print(f"  [FAILED] {result.name}  ({result.elapsed:.1f}s) - {exit_desc}")

    return result


def print_summary(results: list[TestResult], host: str, port: int):
    """打印测试汇总报告。"""
    passed = [r for r in results if r.status == "passed"]
    failed = [r for r in results if r.status in ("failed", "error")]
    timeout = [r for r in results if r.status == "timeout"]
    total_time = sum(r.elapsed for r in results)

    print("\n" + "=" * 70)
    print("                         测试汇总报告")
    print("=" * 70)
    print(f"  MCP Server: {host}:{port}")
    print(f"  总用例数:   {len(results)}")
    print(f"  通过:       {len(passed)}  ✅")
    print(f"  失败:       {len(failed)}  ❌")
    print(f"  超时:       {len(timeout)}  ⏰")
    print(f"  总耗时:     {total_time:.1f}s  ({total_time/60:.1f}min)")
    print("-" * 70)

    if failed or timeout:
        print("\n  失败/超时详情:")
        for r in results:
            if r.status in ("failed", "timeout", "error"):
                print(f"    ❌ {r.name}: {r.error_msg}  ({r.elapsed:.1f}s)")
                lines = r.stdout.strip().splitlines()
                if lines:
                    print(f"       最后输出:")
                    for line in lines[-5:]:
                        print(f"         {line}")
                if r.stderr.strip():
                    err_lines = r.stderr.strip().splitlines()
                    print(f"       错误输出:")
                    for line in err_lines[-3:]:
                        print(f"         {line}")

    print("\n  全部结果:")
    for r in results:
        icon = "✅" if r.status == "passed" else "❌" if r.status in ("failed", "error") else "⏰"
        print(f"    {icon} {r.name:30s}  {r.status.upper():8s}  {r.elapsed:8.1f}s  {r.desc}")

    print("=" * 70)

    if failed or timeout:
        return 1
    return 0


async def main() -> int:
    host, port, parallel, list_only, timeout, filter_kw = parse_args()

    print("=" * 70)
    print("           MCP Client Example 测试运行器")
    print("=" * 70)
    print(f"  项目根目录: {ROOT}")
    print(f"  Python:     {PYTHON}")
    print(f"  MCP Server: {host}:{port}")
    print(f"  执行模式:   {'并行' if parallel else '串行'}")
    print(f"  单测超时:   {timeout}s ({timeout/60:.0f}min)")
    if filter_kw:
        print(f"  过滤条件:   {filter_kw}")
    print("=" * 70)

    # 检查前置条件
    issues = check_prerequisites()
    if issues:
        print("\n[ERROR] 前置检查未通过:")
        for issue in issues:
            print(f"  - {issue}")
        return 1

    # 筛选测试用例
    test_cases = TEST_CASES
    if filter_kw:
        test_cases = [tc for tc in test_cases if filter_kw in tc["name"].lower()]

    print(f"\n  待运行测试数: {len(test_cases)}")

    if list_only:
        print("\n  测试用例列表:")
        for tc in test_cases:
            print(f"    - {tc['name']:30s}  {tc['desc']}")
            print(f"      命令: python {tc['script']} {' '.join(tc['args'])} --host {host} --port {port}")
        return 0

    # 提示
    if not parallel and len(test_cases) > 1:
        print("\n  提示: 这些测试会调用 MCP server 上的真实翻译服务，每个测试可能耗时较长。")
        print("        使用 --parallel 可并行执行，使用 --filter 可只运行特定测试。")
        print(f"\n  请确保 MCP server 已在运行: python -m backend.mcp_server --http --host {host} --port {port}")

    # 运行测试
    results: list[TestResult] = []

    if parallel:
        semaphore = asyncio.Semaphore(2)
        tasks = [run_single_test(tc, host, port, timeout, semaphore) for tc in test_cases]
        results = await asyncio.gather(*tasks)
    else:
        for tc in test_cases:
            result = await run_single_test(tc, host, port, timeout)
            results.append(result)

    return print_summary(results, host, port)


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
