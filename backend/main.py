"""
Orchestra Backend —— FastAPI 入口。

启动方式（在项目根目录执行）：
    python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 5001
"""

import os
import sys
import webbrowser
import asyncio
from contextlib import asynccontextmanager
from typing import Optional

# Windows 中文区域（GBK）下 stdout 为管道/重定向时，print 的 ✓/⚠ 会
# UnicodeEncodeError 崩溃（v1.4.0 Windows 真机实测）；统一 UTF-8，
# 真实控制台路径（启动.bat 走 WinConsoleIO）不受影响
if sys.stdout:
    sys.stdout.reconfigure(encoding="utf-8")
if sys.stderr:
    sys.stderr.reconfigure(encoding="utf-8")

import yaml
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from pydantic import BaseModel

from .agent_runner import agent_runner, BOSS_CODE
from .config_loader import (get_config, get_project_root, get_llm_base_url,
                            get_user_flag, reload_config)
from .record_manager import record_manager
from .sse_manager import sse_manager, AppStatus

# 前端构建产物目录：存在则由后端直接托管页面（发布形态，无需另跑 Vite/Node）
_DIST = get_project_root() / "frontend" / "dist"

# 服务事件循环引用：桌面壳关窗时从主线程安全触发 SSE 干净退出（prepare_exit）
_loop: Optional[asyncio.AbstractEventLoop] = None


def prepare_exit() -> None:
    """线程安全地让所有 SSE 连接干净退出。桌面壳关窗后、停服前调用。

    SSE 是永不主动结束的流；不先关它们，uvicorn 优雅停服会一直等
    （表现为关窗后进程拖好几秒）。sse_manager.shutdown 让每个流的
    generator 正常 return → 连接正常完成 → 停服无需等待。
    """
    if _loop is not None and _loop.is_running():
        _loop.call_soon_threadsafe(
            lambda: asyncio.ensure_future(sse_manager.shutdown()))


# ============ 生命周期 ============

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用启动/关闭时的生命周期管理"""
    global _loop
    _loop = asyncio.get_running_loop()
    try:
        config = get_config()
        print(f"✓ 配置加载成功")
        print(f"  - 平台: {config.platform.get('name', 'unknown')}")
        print(f"  - 搜索城市: {[c['name'] for c in config.search.get('cities', [])]}")
        print(f"  - Web UI: {config.web_ui.host}:{config.web_ui.port}")

        # 启动健康检查
        import os, shutil
        from pathlib import Path
        dsk = os.getenv("DEEPSEEK_API_KEY", "")
        if not dsk or dsk.startswith("your_"):
            print("⚠ DEEPSEEK_API_KEY 未设置，请编辑 .env 文件")
        resume_path = Path(config.resume.get("pdf_path", "my_resume.pdf"))
        if not resume_path.is_absolute():
            resume_path = get_project_root() / resume_path
        if not resume_path.exists():
            print(f"⚠ 简历未找到: {resume_path}")
        if not shutil.which("google-chrome") and not shutil.which("Google Chrome") and not Path("/Applications/Google Chrome.app").exists():
            print("⚠ 未检测到 Google Chrome")
    except Exception as e:
        print(f"⚠ 配置加载警告: {e}")

    if config.web_ui.auto_open and not os.environ.get("ORCHESTRA_SHELL"):
        # 桌面壳形态（launcher.py）由 pywebview 开窗口，不再另开浏览器标签页
        try:
            if (_DIST / "index.html").exists():
                webbrowser.open(f"http://127.0.0.1:{config.web_ui.port}")
            else:
                webbrowser.open("http://localhost:5173")
        except Exception:
            pass

    yield

    await sse_manager.shutdown()
    if agent_runner.is_running or agent_runner.is_sending:
        print("正在停止后台任务...")
        await agent_runner.stop()
    # 退出时始终关闭 Agent Chrome——孤儿 Chrome 会锁住 data/chrome-profile，
    # 下次启动登录态读取失败（桌面壳"关窗即退净"的最后一环）
    await agent_runner.close_browser()
    # 埋点：本次会话"评了没发"的岗位——评分误报候选信号
    try:
        from .agent_runner import behavior_log
        unsent = [{"company": r.get("company"), "position": r.get("position"),
                   "score": r.get("score")}
                  for r in record_manager.get_all_records() if r.get("status") == "dry_run"]
        if unsent:
            behavior_log({"event": "session_skip", "unsent": unsent})
    except Exception as e:
        print(f"⚠ 埋点写入失败: {e}")
    # 关闭共享 httpx 客户端（此前四个模块各养一个，已收敛到 backend/llm.py）
    from . import llm as _llm
    await _llm.aclose()


# ============ FastAPI 实例 ============

config = get_config()

app = FastAPI(
    title="Orchestra API",
    version="1.0.0",
    description="Orchestra — AI Agent 编排框架，BOSS 直聘智能求职应用",
    lifespan=lifespan,
)

# CORS —— 允许本地前端访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173","http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============ 数据模型 ============

class StatusResponse(BaseModel):
    status: str = "idle"
    is_running: bool = False
    tier_counts: dict = {}
    total_applied: int = 0
    pending_count: int = 0


class StartResponse(BaseModel):
    success: bool
    message: str


class UploadResumeResponse(BaseModel):
    ok: bool
    filename: str = ""

# ============ REST API ============

@app.post("/api/upload-resume", response_model=UploadResumeResponse,
          summary="上传简历", description="上传 PDF 简历文件")
async def upload_resume(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="请上传 PDF 文件")
    save_path = get_project_root() / "my_resume.pdf"
    # 上传时即验证内容可解析且文本足够（防恶意/误传：图片版、扫描件、改名文件）——
    # 否则垃圾 PDF 一直躺到运行阶段才炸，买家排查成本高
    tmp_path = save_path.with_suffix(".pdf.tmp")
    content = await file.read()
    with open(tmp_path, "wb") as f:
        f.write(content)
    try:
        from pdfminer.high_level import extract_text
        text = extract_text(str(tmp_path)) or ""
    except Exception:
        text = ""
    if len(text.strip()) < 50:
        tmp_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400,
            detail="这份 PDF 解析不出足够的文字内容——可能是扫描件/图片版简历或文件损坏，请上传可选中文字的文字版 PDF")
    try:
        os.replace(tmp_path, save_path)
    except PermissionError:
        tmp_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400,
            detail="简历文件被其他程序占用（可能正被 PDF 阅读器打开），请关闭后重试")
    return UploadResumeResponse(ok=True, filename=file.filename)


@app.get("/api/status", response_model=StatusResponse,
          summary="获取运行状态", description="返回 Agent 是否运行中、已匹配数量、分层统计")
async def get_status():
    """获取当前运行状态"""
    return StatusResponse(
        status=sse_manager.status.value,
        is_running=agent_runner.is_running,
        tier_counts=record_manager.get_tier_counts(),
        total_applied=record_manager.get_record_count(),
        pending_count=len(record_manager.get_all_pending()),
    )


@app.post("/api/start", response_model=StartResponse,
          summary="启动任务", description="启动 Agent 搜索评分流程：开浏览器→登录→搜→评→分层→问候语")
async def start_task():
    """启动投递任务。开始前预检 DeepSeek Key（仅在拿到确定性结论时拦截，
    网络异常不阻塞——运行链路自身有失败熔断）。"""
    key = os.getenv("DEEPSEEK_API_KEY", "")
    if key and not key.startswith("your_"):
        pre = await _check_key(key)
        if pre["valid"] is False and ("无效" in pre["message"] or "余额" in pre["message"]):
            raise HTTPException(status_code=409, detail=pre["message"])
        # 余额接口给出了数值且为 0 → 提前拦截（否则跑到评分阶段才 402）
        if pre.get("balance"):
            try:
                if float(pre["balance"].split()[0]) <= 0:
                    raise HTTPException(status_code=409,
                        detail="DeepSeek 余额不足——请到 platform.deepseek.com 充值后重试")
            except ValueError:
                pass
    try:
        await agent_runner.start()
        return StartResponse(success=True, message="投递任务已启动")
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"启动失败: {str(e)}")


@app.post("/api/stop", response_model=StartResponse,
          summary="停止任务", description="停止正在运行的 Agent 任务，关闭 Chrome")
async def stop_task():
    """停止投递任务"""
    try:
        await agent_runner.stop()
        return StartResponse(success=True, message="投递任务已停止")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"停止失败: {str(e)}")


@app.get("/api/records",
         summary="获取投递记录", description="返回当前会话所有已评分的岗位记录")
async def get_records():
    """获取所有投递记录"""
    return {
        "records": record_manager.get_all_records(),
        "total": record_manager.get_record_count(),
    }


@app.get("/api/pending",
         summary="获取待选区", description="低置信度候选保留在此，最多 5 条")
async def get_pending():
    """获取待选区列表"""
    return {
        "items": record_manager.get_all_pending(),
        "count": len(record_manager.get_all_pending()),
    }


# ============ 设置（自服务：在界面上填 Key / 城市 / 关键词，免改配置文件） ============

class CitySetting(BaseModel):
    name: str
    min_salary: int = 0

class SettingsRequest(BaseModel):
    deepseek_key: str = ""
    cities: list[CitySetting] = []
    primary_keywords: list[str] = []
    wizard_done: Optional[bool] = None


class VerifyKeyRequest(BaseModel):
    key: str


def _write_env_key(key: str) -> None:
    """把 DEEPSEEK_API_KEY 写入 .env（保留其他行），并立即生效到当前进程"""
    env_path = get_project_root() / ".env"
    lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []
    kept, replaced = [], False
    for line in lines:
        if line.startswith("DEEPSEEK_API_KEY="):
            kept.append(f"DEEPSEEK_API_KEY={key}")
            replaced = True
        else:
            kept.append(line)
    if not replaced:
        kept.append(f"DEEPSEEK_API_KEY={key}")
    env_path.write_text("\n".join(kept) + "\n", encoding="utf-8")
    os.environ["DEEPSEEK_API_KEY"] = key


@app.get("/api/settings",
         summary="读取设置", description="返回 Key 配置状态、支持的城市与当前搜索设置")
async def get_settings():
    cfg = get_config()
    key = os.getenv("DEEPSEEK_API_KEY", "")
    resume_path = Path(cfg.resume.get("pdf_path", "my_resume.pdf"))
    if not resume_path.is_absolute():
        resume_path = get_project_root() / resume_path
    return {
        "key_configured": bool(key) and not key.startswith("your_"),
        "key_tail": key[-4:] if len(key) >= 8 else "",
        "supported_cities": list(BOSS_CODE.keys()),
        "cities": cfg.search.get("cities", []),
        "primary_keywords": cfg.search.get("primary_keywords", []),
        "wizard_done": get_user_flag("wizard_done"),
        "resume_uploaded": resume_path.exists(),
    }


@app.post("/api/settings",
          summary="保存设置", description="Key 写入 .env、城市/关键词写入 data/user_settings.yaml，立即生效")
async def save_settings(req: SettingsRequest):
    result = {"ok": True, "key_valid": None, "message": ""}
    try:
        # ---- DeepSeek Key ----
        key = req.deepseek_key.strip()
        if key:
            # 保存前轻量校验（调一次模型列表；网络异常不阻塞保存）
            try:
                import httpx
                async with httpx.AsyncClient(timeout=10.0) as client:
                    r = await client.get(f"{get_llm_base_url('deepseek')}/models",
                                         headers={"Authorization": f"Bearer {key}"})
                    result["key_valid"] = r.status_code == 200
                    if r.status_code == 401:
                        result["ok"] = False
                        result["message"] = "DeepSeek Key 无效（401），请检查后重填"
                        return result
            except Exception as e:
                print(f"⚠ Key 校验请求失败（不阻塞保存）: {e}")
            _write_env_key(key)
            result["message"] = "Key 已保存" + ("（校验通过）" if result["key_valid"] else "")

        # ---- 城市 / 关键词 / 向导标记 ----
        # 合并旧值而非整体重建：否则只保存 Key 会把已存的城市清空（向导分步保存的坑）
        root = get_project_root()
        (root / "data").mkdir(parents=True, exist_ok=True)
        us_path = root / "data" / "user_settings.yaml"
        try:
            overrides = yaml.safe_load(us_path.read_text(encoding="utf-8")) if us_path.exists() else {}
        except Exception:
            overrides = {}
        if not isinstance(overrides, dict):
            overrides = {}
        search = overrides.setdefault("search", {})
        if req.cities:
            supported = [c for c in req.cities if c.name in BOSS_CODE]
            dropped = len(req.cities) - len(supported)
            if dropped:
                result["message"] += f"（{dropped} 个不支持的城市被忽略）"
            search["cities"] = [
                {"name": c.name, "min_salary": c.min_salary} for c in supported]
        if req.primary_keywords:
            search["primary_keywords"] = [
                k.strip() for k in req.primary_keywords if k.strip()]
        if req.wizard_done is not None:
            overrides["wizard_done"] = req.wizard_done
        us_path.write_text(
            yaml.safe_dump(overrides, allow_unicode=True), encoding="utf-8")

        reload_config()
        if not result["message"]:
            result["message"] = "设置已保存"
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"保存失败: {e}")


async def _check_key(key: str) -> dict:
    """校验 DeepSeek Key（零成本）：余额接口优先，代理 base_url 无此端点时回退模型列表。

    向导 verify-key 与 /api/start 启动预检共用。
    """
    import httpx
    base = get_llm_base_url("deepseek").rstrip("/")
    balance_url = (base[:-3] if base.endswith("/v1") else base) + "/user/balance"
    headers = {"Authorization": f"Bearer {key}"}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(balance_url, headers=headers)
            if r.status_code == 401:
                return {"valid": False, "balance": None, "message": "DeepSeek Key 无效，请检查是否复制完整"}
            if r.status_code == 200:
                infos = (r.json().get("balance_infos") or [])
                balance = next((f"{i.get('total_balance')} {i.get('currency')}"
                                for i in infos if i.get("currency") == "CNY"), None)
                return {"valid": True, "balance": balance,
                        "message": "Key 有效" + (f"，余额 {balance}" if balance else "")}
            # 自定义 base_url/代理可能没有 balance 端点 → 回退模型列表校验
            r2 = await client.get(f"{base}/models", headers=headers)
            if r2.status_code == 200:
                return {"valid": True, "balance": None, "message": "Key 有效"}
            if r2.status_code == 401:
                return {"valid": False, "balance": None, "message": "DeepSeek Key 无效，请检查是否复制完整"}
            return {"valid": False, "balance": None,
                    "message": f"校验失败（HTTP {r.status_code}），请稍后重试"}
    except httpx.HTTPError as e:
        return {"valid": False, "balance": None, "message": f"网络异常，无法连接 DeepSeek：{e}"}


@app.post("/api/verify-key",
          summary="校验 DeepSeek Key", description="粘贴即校验：返回有效性与余额，不保存")
async def verify_key(req: VerifyKeyRequest):
    """向导第 3 步用：粘贴即校验。"""
    key = req.key.strip()
    if not key:
        raise HTTPException(status_code=400, detail="请输入 Key")
    return await _check_key(key)


@app.post("/api/login", response_model=StartResponse,
          summary="首跑向导：仅登录", description="启动浏览器扫码登录并验证 cookie，不进入搜索评分")
async def login_only():
    """向导第 5 步用；登录态保存后，之后正式运行免扫码。"""
    try:
        ok = await agent_runner.login_only()
        return StartResponse(success=ok, message="登录成功" if ok else "登录未完成")
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"登录引导失败: {e}")


# ============ SSE 端点 ============

@app.get("/api/events",
         summary="SSE 实时推送", description="前端通过 EventSource 订阅：status/record/complete/error 四种事件")
async def sse_events():
    """SSE 事件流 —— 前端通过 EventSource 订阅"""
    return await sse_manager.subscribe()


# ============ 发送招呼语 ============

class SendJob(BaseModel):
    securityId: str
    encryptJobId: str = ""
    greeting: str
    company: str = ""

class SendRequest(BaseModel):
    jobs: list[SendJob]


@app.post("/api/send",
          summary="批量发送招呼语", description="将前端选中的岗位逐条发送：friend/add.json 建关系 → CDP 输入自定义文案")
async def send_greetings(req: SendRequest):
    """发送招呼语给前端选中的职位"""
    if not agent_runner._tab:
        raise HTTPException(status_code=400, detail="浏览器未就绪，请先运行搜索评分")
    if agent_runner.is_running:
        raise HTTPException(status_code=409, detail="搜索评分任务运行中，请先停止")
    if agent_runner.is_sending:
        raise HTTPException(status_code=409, detail="正在发送招呼语，请等待完成")

    jobs = [{"securityId": j.securityId, "encryptJobId": j.encryptJobId,
             "greeting": j.greeting, "company": j.company}
            for j in req.jobs]
    return await agent_runner.send_greetings(jobs)


@app.post("/api/close",
          summary="关闭浏览器", description="手动关闭 nodriver Chrome 浏览器")
async def close_browser():
    """关闭浏览器"""
    if agent_runner.is_sending:
        raise HTTPException(status_code=409, detail="正在发送招呼语，请先等待完成或停止")
    await agent_runner.close_browser()
    return {"ok": True, "message": "浏览器已关闭"}


# ============ 根路径：有构建产物直接给页面，开发模式跳转 Vite ============

@app.get("/", include_in_schema=False)
async def root():
    if (_DIST / "index.html").exists():
        return FileResponse(_DIST / "index.html")
    from starlette.responses import RedirectResponse
    return RedirectResponse(url="http://localhost:5173")


# ============ 健康检查 ============

@app.get("/api/health",
         summary="健康检查", description="返回服务运行状态")
async def health():
    import os
    status = "ok"
    checks = {"api_key": bool(os.getenv("DEEPSEEK_API_KEY","")),
              "chrome_alive": agent_runner._browser is not None,
              "tab_alive": agent_runner._tab is not None}
    if not checks["api_key"]:
        status = "degraded"
    return {"status": status, "service": "Orchestra", "checks": checks}


# ============ 前端静态托管（发布形态） ============

if (_DIST / "index.html").exists():
    app.mount("/assets", StaticFiles(directory=_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str):
        """SPA 回退：非 /api 路径回 index.html（前端路由）；未知 /api 路径 404"""
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not Found")
        if full_path:
            candidate = (_DIST / full_path).resolve()
            # 防路径穿越：解析后的路径必须仍在 dist 内
            if str(candidate).startswith(str(_DIST.resolve())) and candidate.is_file():
                return FileResponse(candidate)
        return FileResponse(_DIST / "index.html")


# ============ 直接运行 ============

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host=config.web_ui.host,
        port=config.web_ui.port,
        reload=True,
    )
