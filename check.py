#!/usr/bin/env python3
"""环境检查——启动前跑一遍，确认所有依赖就绪"""
import os, sys, shutil, subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OK = "✅"; WARN = "⚠️"; FAIL = "❌"

def check_python():
    v = sys.version_info
    if v >= (3,12):
        print(f"{OK} Python {v.major}.{v.minor}.{v.micro}")
        return True
    print(f"{FAIL} Python {v.major}.{v.minor}（需要 3.12+）")
    return False

def check_node():
    try:
        r = subprocess.run(["node","--version"], capture_output=True, text=True, timeout=5)
        if r.returncode == 0:
            print(f"{OK} Node {r.stdout.strip()}")
            return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    print(f"{FAIL} Node.js 未安装（需要 18+）")
    return False

def check_chrome():
    paths = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",  # macOS
        "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",    # Windows
        shutil.which("google-chrome") or "",                              # Linux
    ]
    for p in paths:
        if p and Path(p).exists():
            print(f"{OK} Chrome: {p}")
            return True
    print(f"{FAIL} Google Chrome 未找到")
    return False

def check_api_key():
    # 加载 .env
    env_path = ROOT / ".env"
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line.startswith("DEEPSEEK_API_KEY="):
                    val = line.split("=",1)[1]
                    if val and not val.startswith("your_"):
                        print(f"{OK} DEEPSEEK_API_KEY 已设置")
                        return True
                    print(f"{WARN} DEEPSEEK_API_KEY 未设置（AI 功能不可用）")
                    return False
    print(f"{WARN} .env 文件不存在，请复制 .env.example 并填入 API Key")
    return False

def check_resume():
    import yaml
    config_path = ROOT / "config.yaml"
    if config_path.exists():
        cfg = yaml.safe_load(open(config_path))
        pdf = cfg.get("resume",{}).get("pdf_path","my_resume.pdf")
        pdf_path = Path(pdf) if Path(pdf).is_absolute() else ROOT / pdf
        if pdf_path.exists():
            print(f"{OK} 简历: {pdf_path}")
            return True
        print(f"{WARN} 简历未找到: {pdf_path}")
        return False
    print(f"{WARN} config.yaml 不存在")
    return False

def check_frontend():
    nm = ROOT / "frontend" / "node_modules"
    if nm.exists() and any(nm.iterdir()):
        print(f"{OK} 前端依赖已安装")
        return True
    print(f"{WARN} 前端依赖未安装，请运行: cd frontend && npm install")
    return False

def main():
    print(f"\n{'='*40}")
    print("Orchestra 环境检查")
    print(f"{'='*40}\n")
    results = [
        check_python(),
        check_node(),
        check_chrome(),
        check_api_key(),
        check_resume(),
        check_frontend(),
    ]
    print(f"\n{'='*40}")
    passed = sum(results)
    total = len(results)
    if passed == total:
        print(f"{OK} 全部 {total} 项通过，可以启动项目")
    else:
        print(f"{WARN} {passed}/{total} 项通过，{total-passed} 项需要处理")
    print()

if __name__ == "__main__":
    main()
