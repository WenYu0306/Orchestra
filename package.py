#!/usr/bin/env python3
"""发布打包 —— 产出「解压 → 双击 → 界面填 Key → 开始」的自服务压缩包。

用法（项目根目录）:
    .venv/bin/python package.py

流程:
    1. 构建前端（frontend/dist 已存在则跳过）
    2. pyinstaller 把后端打包为当前平台的可执行文件（onedir）
    3. 组装 dist-release/Orchestra-<版本>/Orchestra/:
       可执行文件 + frontend/dist + 干净的 config.yaml + .env.example + 使用手册 + 双击入口
    4. 敏感内容扫描（fail-closed）: .env / 简历 / data / .git / node_modules 等
       一旦混入发布包，删除产物并以非零码退出 —— 宁可不打包，不能把开发者数据卖出去
    5. 压缩为 dist-release/Orchestra-<版本>-<平台>.zip

注意: pyinstaller 无法跨平台交叉编译 —— Windows 包需在 Windows 上运行本脚本
（可用 GitHub Actions 的 windows runner，本仓库是公开的，Actions 免费）。
"""
import os
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

# Windows 管道输出默认 cp1252，本脚本 print 的 ⚙/✅/❌ 会直接 UnicodeEncodeError
# （2026-11-14 Windows CI 实测崩溃）；强制 UTF-8，macOS/Linux 上是无操作
sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent
RELEASE_DIR = ROOT / "dist-release"
PYI_DIST = ROOT / ".pyi-out"
PYI_WORK = ROOT / ".pyi-work"

# 发布包内绝不允许出现的内容（fail-closed 扫描）
FORBIDDEN = [
    r"(^|/)\.env$",          # 真实 .env（.env.example 允许）
    r"\.pdf$",               # 简历
    r"(^|/)data/",           # 运行数据（投递记录/日志/登录态）
    r"\.git",
    r"(^|/)notes/",
    r"(^|/)tools/",
    r"\.venv",
    r"node_modules",
    r"__pycache__",
    r"\.pyc$",
    r"\.DS_Store",
    r"my_resume",
    r"chrome-profile",
    r"\.log$",
    r"\.corrupt\.",
]


def get_version() -> str:
    m = re.search(r"^## \[([\d.]+)\]", (ROOT / "CHANGELOG.md").read_text(encoding="utf-8"), re.M)
    return m.group(1) if m else "0.0.0"


def build_frontend() -> None:
    if (ROOT / "frontend" / "dist" / "index.html").exists():
        return
    print("⚙ 构建前端 (npm run build) ...")
    subprocess.run(["npm", "run", "build"], cwd=ROOT / "frontend", check=True)


def build_backend() -> None:
    print("⚙ pyinstaller 打包后端 ...")
    subprocess.run(
        [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
         "--name", "Orchestra", "--onedir",
         "--distpath", str(PYI_DIST), "--workpath", str(PYI_WORK),
         str(ROOT / "launcher.py")],
        cwd=ROOT, check=True)


def assemble(ver: str, tag: str) -> Path:
    app = RELEASE_DIR / f"Orchestra-{ver}" / "Orchestra"
    if app.parent.exists():
        shutil.rmtree(app.parent)
    app.mkdir(parents=True)

    # pyinstaller onedir 产物（可执行文件 + _internal/）
    for item in (PYI_DIST / "Orchestra").iterdir():
        if item.is_dir():
            shutil.copytree(item, app / item.name,
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        else:
            shutil.copy2(item, app / item.name)

    # 前端构建产物（后端直接托管，买家无需 Node）
    shutil.copytree(ROOT / "frontend" / "dist", app / "frontend" / "dist")

    # 干净的 config.yaml：从 example 生成，仅打开 auto_open
    cfg = (ROOT / "config.yaml.example").read_text(encoding="utf-8")
    cfg = cfg.replace("auto_open: false", "auto_open: true")
    (app / "config.yaml").write_text(cfg, encoding="utf-8")

    shutil.copy2(ROOT / ".env.example", app / ".env.example")

    # 使用手册：Windows 用 docx（双击可开），mac 用 md（Quick Look 可预览）
    manual_name = "使用手册.docx" if tag == "windows" else "使用手册.md"
    shutil.copy2(ROOT / "docs" / manual_name, app / manual_name)

    # 双击入口（两个平台都放，与可执行文件平台匹配的那个生效）
    (app / "启动.command").write_text(
        '#!/bin/bash\ncd "$(dirname "$0")"\n./Orchestra\n', encoding="utf-8")
    (app / "启动.command").chmod(0o755)
    # 引号包 exe 路径：NoDefaultCurrentDirectoryInExePath=1 环境下 cmd 不搜索
    # 当前目录，裸文件名 100% 崩（v1.6.0 Windows 验收发现）；条件 pause：仅异常
    # 退出时停住供排障，正常退出不留常驻 cmd（兑现"关窗即完全退出"）
    # PowerShell Unblock-File：浏览器下载的 zip 经资源管理器解压会把 MOTW 传播到
    # 全部文件（v1.6.3 买家路径验收实测 301/301），.NET CLR 拒绝加载带 MOTW 的
    # pythonnet 程序集 → 双击即崩。bat 首步自动清标记，用户点完「运行」无感知
    (app / "启动.bat").write_bytes(
        ("@echo off\r\nchcp 65001 >nul\r\ncd /d %~dp0\r\n"
         "powershell -NoProfile -ExecutionPolicy Bypass -Command "
         "\"Get-ChildItem -LiteralPath '%~dp0.' -Recurse | Unblock-File\" 2>nul\r\n"
         '"%~dp0Orchestra.exe"\r\nif errorlevel 1 pause\r\n').encode("utf-8"))
    return app


def zip_and_scan(app: Path, zip_path: Path) -> int:
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in sorted(app.rglob("*")):
            if p.is_file():
                # as_posix: Windows 下 zipfile 归档名必须用 /，fail-closed 扫描的
                # 正则（(^|/)\.env$ 等）依赖这个分隔符
                zf.write(p, p.relative_to(app.parent).as_posix())
    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
    bad = sorted({n for n in names for pat in FORBIDDEN if re.search(pat, n)})
    if bad:
        zip_path.unlink(missing_ok=True)
        sys.exit(f"❌ 发布包混入敏感内容，已删除产物: {bad[:10]}")
    return len(names)


def main() -> None:
    ver = get_version()
    build_frontend()
    build_backend()
    tag = {"darwin": "macos", "win32": "windows"}.get(sys.platform, sys.platform)
    app = assemble(ver, tag)
    zip_path = RELEASE_DIR / f"Orchestra-{ver}-{tag}.zip"
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    n = zip_and_scan(app, zip_path)
    print(f"✅ 发布包: {zip_path}")
    print(f"   {n} 个文件, {zip_path.stat().st_size / 1024 / 1024:.1f} MB")


if __name__ == "__main__":
    main()
