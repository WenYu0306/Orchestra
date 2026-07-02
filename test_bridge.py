"""
Bridge 连接诊断脚本。

测试：
1. Python Bridge 服务器能否启动
2. Extension 能否通过 ws:// 连接
3. Extension Service Worker 能否被 Port 保活

运行：cd JobHunter && source .venv/bin/activate && python test_bridge.py
"""

import asyncio
import json
import os
import signal
import subprocess
import time
import websockets
from pathlib import Path

PROJECT = Path(__file__).parent
EXT_DIR = PROJECT / "extension"
WS_URI = "ws://127.0.0.1:9223"

# ========== Step 1: 验证 Bridge 服务器 ==========

async def test_bridge_server():
    print("=" * 60)
    print("Step 1: 测试 Bridge WebSocket 服务器")
    print("=" * 60)

    from backend.extension_bridge import bridge
    await bridge.start(port=9223)

    # 用 websockets 客户端模拟 Extension 连接
    try:
        async with websockets.connect(WS_URI) as ws:
            print("  ✓ ws://127.0.0.1:9223 连接成功")

            # 发一个 ping
            await ws.send(json.dumps({"id": 1, "action": "ping"}))
            resp = await asyncio.wait_for(ws.recv(), timeout=5)
            data = json.loads(resp)
            assert data.get("id") == 1, f"response id mismatch: {data}"
            print(f"  ✓ ping 响应: {data}")

        print("  ✓ Bridge 服务器工作正常\n")
    except Exception as e:
        print(f"  ✗ Bridge 测试失败: {e}\n")
    finally:
        await bridge.stop()
        await asyncio.sleep(0.5)


# ========== Step 2: 验证 Extension 文件完整性 ==========

def test_extension_files():
    print("=" * 60)
    print("Step 2: 验证 Extension 文件")
    print("=" * 60)

    required = ["manifest.json", "background.js", "content.js"]
    for fname in required:
        fpath = EXT_DIR / fname
        if fpath.exists():
            print(f"  ✓ {fname} ({len(fpath.read_text())} bytes)")
        else:
            print(f"  ✗ {fname} 缺失!")
            return False

    # 验证 manifest.json 语法
    import json
    try:
        manifest = json.loads((EXT_DIR / "manifest.json").read_text())
        print(f"  ✓ manifest.json 解析成功 (manifest_version={manifest.get('manifest_version')})")
        # 检查关键字段
        assert manifest.get("manifest_version") == 3, "需要 manifest v3"
        assert "background" in manifest, "缺少 background"
        assert "content_scripts" in manifest, "缺少 content_scripts"
        assert manifest["content_scripts"][0].get("run_at") == "document_start", "需要 run_at: document_start"
        print(f"  ✓ manifest 结构完整")
    except Exception as e:
        print(f"  ✗ manifest 错误: {e}")
        return False

    print()
    return True


# ========== Step 3: 验证 Chrome 能否加载 Extension ==========

def test_chrome_starts():
    print("=" * 60)
    print("Step 3: 测试 Chrome + Extension 启动")
    print("=" * 60)

    chrome_paths = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Google Chrome Canary.app/Contents/MacOS/Google Chrome Canary",
    ]
    chrome = None
    for p in chrome_paths:
        if os.path.exists(p):
            chrome = p
            break
    if not chrome:
        print("  ✗ 找不到 Chrome")
        return

    print(f"  ✓ Chrome: {chrome}")

    # 杀干净
    subprocess.run(["killall", "Google Chrome"], capture_output=True)
    time.sleep(2)

    ext_path = str(EXT_DIR.resolve())
    print(f"  Extension 路径: {ext_path}")

    # 启动 Chrome
    proc = subprocess.Popen(
        [chrome,
         f"--load-extension={ext_path}",
         "--no-first-run",
         "--no-default-browser-check",
         "https://www.baidu.com",  # 先打开一个简单页面，不触发反爬
        ],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )

    print("  Chrome PID:", proc.pid)
    print("  等待 5 秒...")
    time.sleep(5)

    if proc.poll() is not None:
        print(f"  ✗ Chrome 立即退出了 (returncode={proc.returncode})")
        print(f"  stderr: {proc.stderr.read().decode()[:500]}")
    else:
        print("  ✓ Chrome 进程存活")

    print("  (手动关闭 Chrome 窗口继续)")
    print()
    return proc


# ========== Step 4: 完整端到端测试 ==========

async def test_e2e():
    print("=" * 60)
    print("Step 4: 端到端测试 (Bridge + Extension)")
    print("=" * 60)

    from backend.extension_bridge import bridge
    await bridge.start(port=9223)
    print("  [Bridge] 已启动")

    chrome_paths = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    ]
    chrome = None
    for p in chrome_paths:
        if os.path.exists(p):
            chrome = p
            break
    if not chrome:
        print("  ✗ 找不到 Chrome")
        return

    ext_path = str(EXT_DIR.resolve())
    subprocess.run(["killall", "Google Chrome"], capture_output=True)
    await asyncio.sleep(2)

    print(f"  [Chrome] 启动中 (Extension: {ext_path})...")
    subprocess.Popen(
        [chrome,
         f"--load-extension={ext_path}",
         "--no-first-run",
         "--no-default-browser-check",
         "https://www.baidu.com",
        ],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True,
    )

    # 等待 Extension 连接
    print("  等待 Extension 连接 (最多 15 秒)...")
    for i in range(15):
        await asyncio.sleep(1)
        if bridge.is_connected:
            print(f"  ✓ Extension 已连接! ({i+1}秒)")
            break
    else:
        print(f"  ✗ Extension 未连接 (超时)")
        print("  → Chrome 已启动但 Extension 没有连接到 Bridge")
        print("  → 可能原因:")
        print("    1. Service Worker 启动失败 (检查 Extension 是否有 JS 错误)")
        print("    2. ws:// 连接被 Service Worker 环境阻止")
        print("    3. Extension 没被正确加载 (检查 chrome://extensions)")
        print("\n  调试方法:")
        print("    → 在打开的 Chrome 里访问 chrome://extensions")
        print("    → 开启右上角 '开发者模式'")
        print("    → 检查 JobHunter 扩展是否显示 '已加载'")
        print("    → 点击 'Service Worker' 链接看控制台日志")
        await bridge.stop()
        return

    # 发 ping
    try:
        from backend.extension_bridge import bridge as b
        await bridge.navigate("https://www.baidu.com")
        await asyncio.sleep(3)
        img = await bridge.screenshot()
        if img:
            print(f"  ✓ 截图成功 ({len(img)} 字符 base64)")
        else:
            print(f"  ✗ 截图返回空")
    except Exception as e:
        print(f"  ✗ 通信失败: {e}")

    await bridge.stop()
    print()


# ========== 主函数 ==========

async def main():
    print("\n🔍 JobHunter Bridge 诊断")
    print("-" * 60)

    await test_bridge_server()
    test_extension_files()

    print("准备启动 Chrome + Extension 端到端测试...")
    print("(Chrome 窗口会弹出，测试完后手动关闭)\n")
    input("按 Enter 继续...")

    await test_e2e()

    print("=" * 60)
    print("诊断完成。如果 Step 4 失败，请检查:")
    print("  1. Chrome 是否打开了 chrome://extensions 页面")
    print("  2. JobHunter 扩展是否出现且状态为 '已加载'")
    print("  3. 点击 'Service Worker' 链接看是否有 JS 错误")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())
