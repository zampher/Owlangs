import os
import sys
import json
import argparse
from typing import Dict, Any, List, Tuple

import httpx


def red(s: str) -> str:
    return f"\033[31m{s}\033[0m"


def green(s: str) -> str:
    return f"\033[32m{s}\033[0m"


def yellow(s: str) -> str:
    return f"\033[33m{s}\033[0m"


def pretty(obj: Any) -> str:
    try:
        return json.dumps(obj, ensure_ascii=False, indent=2)
    except Exception:
        return str(obj)


async def try_get(client: httpx.AsyncClient, url: str, headers: Dict[str, str]) -> Dict[str, Any]:
    try:
        print(yellow(f"→ GET {url}"))
        print(yellow(f"→ Headers: {headers}"))
        resp = await client.get(url, headers=headers)
        print(yellow(f"← Status: {resp.status_code}"))
        print(yellow(f"← Resp headers: {dict(resp.headers)}"))
        body = None
        try:
            body = resp.json()
        except Exception:
            body = resp.text
        print(yellow(f"← Body: {pretty(body)[:2000]}"))
        return {"ok": resp.status_code == 200, "status": resp.status_code, "body": body}
    except Exception as e:
        print(red(f"Request failed: {e}"))
        return {"ok": False, "error": str(e)}


async def run_mineru_tests(
    token: str,
    base: str,
    test_mode: str,
    task_id: str = None,
) -> None:
    async with httpx.AsyncClient(timeout=15.0) as client:
        print("\n" + green("== MinerU API Test =="))
        print(yellow(f"Base URL: {base}"))
        print(yellow(f"Token head: {token[:20]}..."))
        print(yellow(f"Test mode: {test_mode}"))

        # 根据文档，MinerU 使用 Authorization: Bearer {token} 格式
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}"
        }

        if test_mode == "connectivity":
            await test_connectivity(client, base, headers)
        elif test_mode == "create-task":
            await test_create_task(client, base, headers)
        elif test_mode == "get-task":
            await test_get_task(client, base, headers, task_id)


async def test_connectivity(client: httpx.AsyncClient, base: str, headers: Dict[str, str]) -> None:
    """测试连接性 - 通过创建任务来验证 API Key 是否有效"""
    print("\n" + green("-- Testing API Key validity by creating a test task --"))
    
    # 使用文档中的示例数据创建任务
    test_data = {
        "url": "https://cdn-mineru.openxlab.org.cn/demo/example.pdf",
        "is_ocr": True,
        "enable_formula": False,
    }
    
    try:
        print(f"→ POST {base}/extract/task")
        print(f"→ Headers: {headers}")
        print(f"→ Data: {test_data}")
        
        response = await client.post(f"{base}/extract/task", headers=headers, json=test_data)
        
        print(f"← Status: {response.status_code}")
        print(f"← Headers: {dict(response.headers)}")
        
        try:
            body = response.json()
            print(f"← Body: {json.dumps(body, indent=2)}")
        except json.JSONDecodeError:
            print(f"← Body: {response.text}")
        
        if response.status_code == 200:
            result = body if isinstance(body, dict) else {}
            if result.get("code") == 0:
                print(green("✅ API Key is valid! Connection test successful."))
                print(f"   Task ID: {result.get('data', {}).get('task_id', 'N/A')}")
            else:
                print(red(f"❌ API returned error: {result.get('msg', 'Unknown error')}"))
        elif response.status_code == 401:
            print(red("❌ Authentication failed - API Key is invalid or expired"))
        else:
            print(red(f"❌ Request failed with status {response.status_code}"))
            
    except httpx.RequestError as e:
        print(red(f"❌ Request failed: {e}"))


async def test_create_task(client: httpx.AsyncClient, base: str, headers: Dict[str, str]) -> None:
    """测试创建任务功能"""
    print("\n" + green("-- Testing task creation --"))
    
    test_data = {
        "url": "https://cdn-mineru.openxlab.org.cn/demo/example.pdf",
        "is_ocr": True,
        "enable_formula": False,
        "data_id": "test_connectivity_check"
    }
    
    try:
        print(f"→ POST {base}/extract/task")
        print(f"→ Headers: {headers}")
        print(f"→ Data: {test_data}")
        
        response = await client.post(f"{base}/extract/task", headers=headers, json=test_data)
        
        print(f"← Status: {response.status_code}")
        print(f"← Headers: {dict(response.headers)}")
        
        try:
            body = response.json()
            print(f"← Body: {json.dumps(body, indent=2)}")
        except json.JSONDecodeError:
            print(f"← Body: {response.text}")
        
        if response.status_code == 200:
            result = body if isinstance(body, dict) else {}
            if result.get("code") == 0:
                task_id = result.get("data", {}).get("task_id")
                print(green(f"✅ Task created successfully! Task ID: {task_id}"))
                print(yellow(f"   You can query this task with: python tools/test_mineru_api.py --test-mode get-task --task-id {task_id}"))
            else:
                print(red(f"❌ Task creation failed: {result.get('msg', 'Unknown error')}"))
        else:
            print(red(f"❌ Request failed with status {response.status_code}"))
            
    except httpx.RequestError as e:
        print(red(f"❌ Request failed: {e}"))


async def test_get_task(client: httpx.AsyncClient, base: str, headers: Dict[str, str], task_id: str) -> None:
    """测试获取任务状态功能"""
    print("\n" + green(f"-- Testing task query for task ID: {task_id} --"))
    
    try:
        print(f"→ GET {base}/extract/task/{task_id}")
        print(f"→ Headers: {headers}")
        
        response = await client.get(f"{base}/extract/task/{task_id}", headers=headers)
        
        print(f"← Status: {response.status_code}")
        print(f"← Headers: {dict(response.headers)}")
        
        try:
            body = response.json()
            print(f"← Body: {json.dumps(body, indent=2)}")
        except json.JSONDecodeError:
            print(f"← Body: {response.text}")
        
        if response.status_code == 200:
            result = body if isinstance(body, dict) else {}
            if result.get("code") == 0:
                task_data = result.get("data", {})
                state = task_data.get("state", "unknown")
                print(green(f"✅ Task query successful! State: {state}"))
                
                if state == "done":
                    zip_url = task_data.get("full_zip_url")
                    if zip_url:
                        print(f"   Download URL: {zip_url}")
                elif state == "running":
                    progress = task_data.get("extract_progress", {})
                    if progress:
                        extracted = progress.get("extracted_pages", 0)
                        total = progress.get("total_pages", 0)
                        print(f"   Progress: {extracted}/{total} pages")
            else:
                print(red(f"❌ Task query failed: {result.get('msg', 'Unknown error')}"))
        elif response.status_code == 404:
            print(red("❌ Task not found - invalid task ID"))
        else:
            print(red(f"❌ Request failed with status {response.status_code}"))
            
    except httpx.RequestError as e:
        print(red(f"❌ Request failed: {e}"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Test MinerU API connectivity (per docs: doc/ref/mineru.txt)")
    parser.add_argument("--token", required=False, default=os.getenv("MINERU_TOKEN"), help="MinerU API token")
    parser.add_argument("--base", required=False, default="https://mineru.net/api/v4", help="MinerU API base URL")
    parser.add_argument(
        "--test-mode",
        required=False,
        default="connectivity",
        choices=["connectivity", "create-task", "get-task"],
        help="Test mode: connectivity (test auth), create-task (test task creation), get-task (test task query)",
    )
    parser.add_argument(
        "--task-id",
        required=False,
        help="Task ID for get-task mode (required for get-task mode)",
    )
    args = parser.parse_args()

    if not args.token:
        print(red("Please provide --token or set MINERU_TOKEN environment variable."))
        sys.exit(2)

    if args.test_mode == "get-task" and not args.task_id:
        print(red("--task-id is required for get-task mode"))
        sys.exit(2)

    try:
        import asyncio
        asyncio.run(
            run_mineru_tests(
                args.token,
                args.base.rstrip('/'),
                args.test_mode,
                args.task_id,
            )
        )
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()


