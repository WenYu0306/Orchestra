#!/usr/bin/env python3
"""打包入口 —— pyinstaller 使用；pywebview 原生窗口壳。源码运行请用 start.sh / start.bat。

打包形态下 __file__ 位于 pyinstaller 的内部目录，config/data/.env 必须落在
用户解压目录里 —— 所以在导入 backend 之前先设置 ORCHESTRA_ROOT
（config_loader.get_project_root 会优先读它）。

壳的行为：
  - uvicorn 跑在后台线程；pywebview 原生窗口（mac: WKWebView / win: WebView2）
    承载界面 —— 无地址栏、无浏览器标签页、不受浏览器扩展干扰
  - 窗口关闭 = 优雅退出：触发 lifespan 停 Agent、关 Chrome、收尾 httpx
    （根治"关掉标签页后端还在跑 → 下次启动端口占用"）
  - ORCHESTRA_SHELL=1 让 main.py 跳过 auto_open（不再另开浏览器标签页）
"""
import os
import sys
import threading
import time
from pathlib import Path

if getattr(sys, "frozen", False):
    os.environ["ORCHESTRA_ROOT"] = str(Path(sys.executable).resolve().parent)
os.environ["ORCHESTRA_SHELL"] = "1"

import uvicorn

from backend.config_loader import get_config
from backend.main import app


def wait_port(port: int, timeout: float = 20.0) -> bool:
    """等后端端口就绪；超时返回 False（端口被占用/启动失败）。"""
    import socket
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1.0):
                return True
        except OSError:
            time.sleep(0.2)
    return False


def main() -> None:
    cfg = get_config()

    config = uvicorn.Config(app, host=cfg.web_ui.host, port=cfg.web_ui.port,
                            log_level="warning",
                            # 关窗后最多等 1 秒就强制掐断残余连接——
                            # 否则 SSE 长连接（/api/events）会让优雅停服无限等待，
                            # 表现为"关窗后进程拖十几秒不退、光标转圈"（实测 3 连接挂起）
                            timeout_graceful_shutdown=1)
    server = uvicorn.Server(config)
    server_thread = threading.Thread(target=server.run, daemon=True)
    server_thread.start()

    try:
        import webview
    except ImportError:
        # 理论上到不了这里（requirements 含 pywebview）——留个明确报错而不是裸崩
        print("缺少 pywebview，无法启动窗口。请用 start.sh / start.bat 以浏览器形式运行。")
        server.should_exit = True
        return

    if not wait_port(cfg.web_ui.port):
        # 后端没起来：常见是端口被占用（已有一个 Orchestra 在跑）——窗口里给人话
        webview.create_window(
            "Orchestra 启动失败",
            html=("<h3>后端启动失败</h3>"
                  f"<p>常见原因：端口 {cfg.web_ui.port} 被占用——可能已有一个 Orchestra 在运行。</p>"
                  "<p>请先关闭另一个 Orchestra 再重试；或编辑 config.yaml 里的 web_ui.port 换一个端口。</p>"),
            width=520, height=300)
        webview.start()
        server.should_exit = True
        return

    webview.create_window(
        "Orchestra · AI 求职助手",
        f"http://127.0.0.1:{cfg.web_ui.port}",
        width=1440, height=900, min_size=(1024, 680))
    webview.start()  # 阻塞到窗口关闭

    # 关窗 → 优雅停服（lifespan：停 Agent、关 Chrome、关 httpx 客户端）
    # 先请 SSE 连接干净退出（否则停服要干等这些永不结束的流——超时强掐兜底仍在）
    from backend.main import prepare_exit
    t_close = time.time()
    print("[shell] 窗口已关闭，正在停服…", flush=True)
    prepare_exit()
    time.sleep(0.15)  # 给事件循环一拍时间真正结束这些流
    server.should_exit = True
    server_thread.join(timeout=10)
    print(f"[shell] 已退出（停服耗时 {time.time() - t_close:.1f}s）", flush=True)


if __name__ == "__main__":
    main()
